"""
FastAPI surface.

Endpoints are coarse on purpose. A chart is cheap to compute and expensive to
round-trip, so /chart returns everything the dashboard needs in one call rather
than making the frontend orchestrate eight requests.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from functools import lru_cache

from fastapi import FastAPI, File, HTTPException, UploadFile, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, field_validator

from import ephemeris as eph
from import kp as kpmod
from import ocr as ocrmod
from import systems as sysmod
from import catalog
from import engine 

app = FastAPI(title="Jyotish API", version="1.0")

ALLOWED = [o for o in os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://your-app.vercel.app").split(",") if o]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED,
    allow_origin_regex=r"https://.*\.vercel\.app",   # covers preview deployments
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ------------------------------------------------------------------- schemas

class BirthData(BaseModel):
    name: str = "Native"
    date: str = Field(..., description="YYYY-MM-DD")
    time: str = Field(..., description="HH:MM or HH:MM:SS, local wall clock")
    tz_offset: float = Field(..., ge=-12, le=14, description="Hours east of UTC at birth")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    node: str = Field("mean", pattern="^(mean|true)$")

    @field_validator("date")
    @classmethod
    def _date(cls, v):
        datetime.strptime(v, "%Y-%m-%d")
        return v

    def to_datetime(self) -> datetime:
        t = self.time if self.time.count(":") == 2 else self.time + ":00"
        return datetime.strptime(f"{self.date} {t}", "%Y-%m-%d %H:%M:%S")


class VarshphalRequest(BirthData):
    year: int
    current_latitude: float | None = None
    current_longitude: float | None = None


def require_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "Bad or missing X-API-Key")


# ------------------------------------------------------------------ assembly

@lru_cache(maxsize=512)
def _chart_cached(date, time, tz, lat, lon, node):
    dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
    return eph.build_chart(dt, tz, lat, lon, node)


def assemble(b: BirthData):
    t = b.time if b.time.count(":") == 2 else b.time + ":00"
    chart = _chart_cached(b.date, t, b.tz_offset, b.latitude, b.longitude, b.node)
    ashtaka = sysmod.ashtakavarga(chart)
    jai = sysmod.jaimini_block(chart)
    sig = kpmod.significators(chart)
    ctx = engine.Ctx(chart, ashtaka, jai, sig)
    return chart, ashtaka, jai, sig, ctx


# ----------------------------------------------------------------- endpoints

@app.get("/health")
def health():
    return {"ok": True, "ephe_path": eph.EPHE_PATH,
            "ephemeris": "swisseph" if os.path.isdir(eph.EPHE_PATH) else "moshier-fallback"}


@app.post("/chart", dependencies=[Depends(require_key)])
def chart(b: BirthData):
    ch, ashtaka, jai, sig, ctx = assemble(b)
    dasha = sysmod.vimshottari(ch.positions["Mo"].lon, b.to_datetime(), levels=3)
    return {
        "name": b.name,
        "chart": ch.dict(),
        "ashtakavarga": ashtaka,
        "jaimini": jai,
        "kp": sig,
        "vimshottari": dasha,
        "chara_dasha": sysmod.chara_dasha(ch),
        "vargas": {
            v: {k: p.vargas[v] for k, p in ch.positions.items()}
            for v in eph.VARGAS
        },
    }


@app.post("/predict/{domain}", dependencies=[Depends(require_key)])
def predict(domain: str, b: BirthData):
    ch, ashtaka, jai, sig, ctx = assemble(b)

    if domain == "job_vs_business":
        return engine.two_sided(catalog.JOB_BUSINESS, ctx, "job", "biz")
    if domain == "love_vs_arranged":
        return engine.two_sided(catalog.LOVE, ctx, "love", "arranged")
    if domain == "spouse":
        return catalog.spouse_portrait(ctx)

    rules = catalog.DOMAINS.get(domain)
    if rules is None:
        raise HTTPException(404, f"Unknown domain. Try one of {sorted(catalog.DOMAINS)}")

    result = engine.cross_check(engine.run(rules, ctx))

    if domain in catalog.TIMING_SETS:
        dasha = sysmod.vimshottari(ch.positions["Mo"].lon, b.to_datetime(), levels=3)
        sigs = catalog.TIMING_SETS[domain](ctx)
        result["windows"] = sysmod.windows_for(
            dasha, sigs, depth=2, after=datetime.utcnow() - timedelta(days=365 * 2))[:12]
        result["significators"] = sorted(sigs)
    return result


@app.post("/predict/all", dependencies=[Depends(require_key)])
def predict_all(b: BirthData):
    ch, ashtaka, jai, sig, ctx = assemble(b)
    dasha = sysmod.vimshottari(ch.positions["Mo"].lon, b.to_datetime(), levels=3)
    out = {}
    for name, rules in catalog.DOMAINS.items():
        r = engine.cross_check(engine.run(rules, ctx))
        if name in catalog.TIMING_SETS:
            r["windows"] = sysmod.windows_for(
                dasha, catalog.TIMING_SETS[name](ctx), depth=2,
                after=datetime.utcnow() - timedelta(days=730))[:8]
        out[name] = r
    out["job_vs_business"] = engine.two_sided(catalog.JOB_BUSINESS, ctx, "job", "biz")
    out["love_vs_arranged"] = engine.two_sided(catalog.LOVE, ctx, "love", "arranged")
    out["spouse"] = catalog.spouse_portrait(ctx)
    return out


@app.post("/varshphal", dependencies=[Depends(require_key)])
def varshphal(b: VarshphalRequest):
    natal, ashtaka, jai, sig, ctx = assemble(b)
    age = b.year - int(b.date[:4])
    if age < 0:
        raise HTTPException(400, "Varshphal year precedes the birth year")

    guess = eph.julian_day(datetime(b.year, int(b.date[5:7]), int(b.date[8:10]), 12), 0)
    jd_sr = eph.solar_return_jd(natal.positions["Su"].lon, guess)

    import swisseph as swe
    y, m, d, h = swe.revjul(jd_sr, swe.GREG_CAL)
    lat = b.current_latitude if b.current_latitude is not None else b.latitude
    lon = b.current_longitude if b.current_longitude is not None else b.longitude
    sr_local = datetime(y, m, d) + timedelta(hours=h + b.tz_offset)
    annual = eph.build_chart(sr_local, b.tz_offset, lat, lon, b.node)

    aspects = sysmod.tajika_aspects(annual)
    day_birth = 6 <= natal.positions["Su"].house <= 12
    return {
        "solar_return_utc": f"{y:04d}-{m:02d}-{d:02d}T{int(h):02d}:{int((h%1)*60):02d}:00Z",
        "annual_chart": annual.dict(),
        "year_lord": sysmod.year_lord(annual, natal, age),
        "tajika_aspects": aspects,
        "kambool": sysmod.kambool(aspects, annual),
        "sahams": sysmod.sahams(annual, day_birth),
    }


@app.post("/transits", dependencies=[Depends(require_key)])
def transits(b: BirthData, on: str | None = None):
    natal, *_ = assemble(b)
    when = datetime.fromisoformat(on) if on else datetime.utcnow()
    now = eph.build_chart(when, 0, b.latitude, b.longitude, b.node)
    out = []
    for k, p in now.positions.items():
        out.append({
            "planet": k,
            "sign": p.sign,
            "house_from_lagna": ((p.sign - natal.lagna_sign) % 12) + 1,
            "house_from_moon": ((p.sign - natal.positions["Mo"].sign) % 12) + 1,
            "retro": p.retro,
            "nakshatra": p.nak_name,
        })
    sade_sati = ((now.positions["Sa"].sign - natal.positions["Mo"].sign) % 12) in (11, 0, 1)
    return {"as_of": when.isoformat(), "transits": out,
            "sade_sati": sade_sati,
            "ruling_planets": kpmod.ruling_planets(now)}


@app.post("/read-chart-image")
async def read_chart_image(file: UploadFile = File(...)):
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(415, "Send a PNG, JPEG or WebP")
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image over 8 MB")

    client = None
    if os.getenv("ANTHROPIC_API_KEY"):
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic()
    result = await ocrmod.read_chart_image(data, client)
    result["partial_chart"] = ocrmod.to_partial_chart(result) if result.get("lagna_sign") else None
    return result
