"""
Sidereal chart construction on Swiss Ephemeris.

Ship the .se1 files (sepl_18.se1, semo_18.se1, seas_18.se1 cover 1800-2400,
about 6 MB total) in ephe/ and point EPHE_PATH at it. Without them pyswisseph
silently falls back to the Moshier analytic theory, which is fine for rashi but
drifts enough to move a cuspal sub-lord. Fail loudly instead of silently.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

import swisseph as swe

EPHE_PATH = os.getenv("EPHE_PATH", "./ephe")
swe.set_ephe_path(EPHE_PATH)
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
         "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
SIGN_LORD = ["Ma", "Ve", "Me", "Mo", "Su", "Me", "Ve", "Ma", "Ju", "Sa", "Sa", "Ju"]

SWE_ID = {
    "Su": swe.SUN, "Mo": swe.MOON, "Ma": swe.MARS, "Me": swe.MERCURY,
    "Ju": swe.JUPITER, "Ve": swe.VENUS, "Sa": swe.SATURN,
    "Ra": swe.MEAN_NODE,          # KP and most Parashari practice use the mean node
}
PLANETS = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"]

FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED

EXALT = {"Su": (0, 10), "Mo": (1, 3), "Ma": (9, 28), "Me": (5, 15),
         "Ju": (3, 5), "Ve": (11, 27), "Sa": (6, 20), "Ra": (1, 20), "Ke": (7, 20)}
OWN = {"Su": [4], "Mo": [3], "Ma": [0, 7], "Me": [2, 5], "Ju": [8, 11],
       "Ve": [1, 6], "Sa": [9, 10], "Ra": [10], "Ke": [7]}
MOOLATRIKONA = {"Su": (4, 0, 20), "Mo": (1, 4, 30), "Ma": (0, 0, 12), "Me": (5, 16, 20),
                "Ju": (8, 0, 10), "Ve": (6, 0, 15), "Sa": (10, 0, 20)}
COMBUST_ORB = {"Mo": 12, "Ma": 17, "Me": 14, "Ju": 11, "Ve": 10, "Sa": 15}
COMBUST_ORB_RETRO = {"Me": 12, "Ve": 8}


def norm(x: float) -> float:
    return x % 360.0


@dataclass
class Position:
    key: str
    lon: float                 # sidereal longitude 0-360
    lat: float
    speed: float
    sign: int                  # 0-11
    deg_in_sign: float
    house: int                 # whole-sign bhava from Lagna
    chalit: int                # Placidus bhava
    retro: bool
    combust: bool
    dignity: str
    nakshatra: int
    nak_name: str
    nak_lord: str
    pada: int
    star_lord: str
    sub_lord: str
    sub_sub_lord: str
    vargas: dict = field(default_factory=dict)


@dataclass
class Chart:
    jd_ut: float
    ayanamsa: float
    lagna: float
    lagna_sign: int
    mc: float
    cusps: list                # 12 Placidus cusp longitudes, sidereal
    positions: dict            # key -> Position
    meta: dict = field(default_factory=dict)

    def dict(self):
        d = asdict(self)
        d["positions"] = {k: asdict(v) if not isinstance(v, dict) else v
                          for k, v in self.positions.items()}
        return d


def julian_day(dt_local: datetime, tz_offset_hours: float) -> float:
    """dt_local is naive wall-clock at the birthplace."""
    ut = dt_local.hour + dt_local.minute / 60 + dt_local.second / 3600 - tz_offset_hours
    return swe.julday(dt_local.year, dt_local.month, dt_local.day, ut, swe.GREG_CAL)


def dignity_of(key: str, sign: int, deg: float) -> str:
    if key in EXALT and EXALT[key][0] == sign:
        return "Exalted"
    if key in EXALT and (EXALT[key][0] + 6) % 12 == sign:
        return "Debilitated"
    if key in MOOLATRIKONA:
        s, lo, hi = MOOLATRIKONA[key]
        if s == sign and lo <= deg <= hi:
            return "Moolatrikona"
    if sign in OWN.get(key, []):
        return "Own sign"
    return "Neutral"


# ---------------------------------------------------------------- divisionals

def navamsa(lon: float) -> int:
    """Cyclic D9. Equivalent to the movable/fixed/dual rule for every sign."""
    return int(lon // (10 / 3)) % 12


def dashamsa(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // 3)
    return (sign + part) % 12 if sign % 2 == 0 else (sign + 8 + part) % 12


def drekkana(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // 10)
    return (sign + part * 4) % 12


def dwadashamsa(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // 2.5)
    return (sign + part) % 12


def saptamsa(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // (30 / 7))
    return (sign + part) % 12 if sign % 2 == 0 else (sign + 6 + part) % 12


def shodashamsa(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // 1.875)
    start = {0: 0, 1: 4, 2: 8}[sign % 3]  # movable/fixed/dual -> Aries/Leo/Sag
    return (start + part) % 12


def vimshamsa(lon: float) -> int:
    sign, part = int(lon // 30), int((lon % 30) // 1.5)
    start = {0: 0, 1: 8, 2: 4}[sign % 3]
    return (start + part) % 12


def trimshamsa(lon: float) -> int:
    """Odd signs: Ma 5, Sa 5, Ju 8, Me 7, Ve 5. Even signs mirrored."""
    d = lon % 30
    odd = int(lon // 30) % 2 == 0
    bands_odd = [(5, 0), (10, 10), (18, 8), (25, 2), (30, 6)]      # Ari Aqu Sag Gem Lib
    bands_even = [(5, 1), (12, 5), (20, 11), (25, 9), (30, 7)]     # Tau Vir Pis Cap Sco
    for edge, sign in (bands_odd if odd else bands_even):
        if d < edge:
            return sign
    return 0


VARGAS = {"D1": lambda l: int(l // 30), "D3": drekkana, "D7": saptamsa, "D9": navamsa,
          "D10": dashamsa, "D12": dwadashamsa, "D16": shodashamsa,
          "D20": vimshamsa, "D30": trimshamsa}


# --------------------------------------------------------------- chart build

def build_chart(dt_local: datetime, tz: float, lat: float, lon: float,
                node: str = "mean") -> Chart:
    jd = julian_day(dt_local, tz)
    ayan = swe.get_ayanamsa_ut(jd)

    # Placidus cusps. houses_ex returns TROPICAL cusps even under FLG_SIDEREAL
    # on some builds, so subtract the ayanamsa explicitly and normalise.
    cusps_trop, ascmc = swe.houses_ex(jd, lat, lon, b"P")
    cusps = [norm(c - ayan) for c in cusps_trop[:12]]
    lagna = norm(ascmc[0] - ayan)
    mc = norm(ascmc[1] - ayan)
    lagna_sign = int(lagna // 30)

    if node == "true":
        SWE_ID["Ra"] = swe.TRUE_NODE

    raw = {}
    for key in ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra"]:
        xx, _ = swe.calc_ut(jd, SWE_ID[key], FLAGS)
        raw[key] = (norm(xx[0]), xx[1], xx[3])
    raw["Ke"] = (norm(raw["Ra"][0] + 180), -raw["Ra"][1], raw["Ra"][2])

    from .kp import nakshatra_of, sub_lords  # local import, avoids a cycle

    sun_lon = raw["Su"][0]
    positions = {}
    for key in PLANETS:
        lon_s, lat_s, spd = raw[key]
        sign = int(lon_s // 30)
        deg = lon_s % 30
        retro = spd < 0 or key in ("Ra", "Ke")
        orb = (COMBUST_ORB_RETRO if retro else COMBUST_ORB).get(key, COMBUST_ORB.get(key, 0))
        sep = abs((lon_s - sun_lon + 180) % 360 - 180)
        nak = nakshatra_of(lon_s)
        star, sub, subsub = sub_lords(lon_s)
        positions[key] = Position(
            key=key, lon=lon_s, lat=lat_s, speed=spd, sign=sign, deg_in_sign=deg,
            house=((sign - lagna_sign) % 12) + 1,
            chalit=placidus_house(lon_s, cusps),
            retro=retro,
            combust=key not in ("Su", "Ra", "Ke") and sep < orb,
            dignity=dignity_of(key, sign, deg),
            nakshatra=nak["index"], nak_name=nak["name"], nak_lord=nak["lord"],
            pada=nak["pada"], star_lord=star, sub_lord=sub, sub_sub_lord=subsub,
            vargas={name: fn(lon_s) for name, fn in VARGAS.items()},
        )

    return Chart(jd_ut=jd, ayanamsa=ayan, lagna=lagna, lagna_sign=lagna_sign,
                 mc=mc, cusps=cusps, positions=positions,
                 meta={"lat": lat, "lon": lon, "tz": tz,
                       "local": dt_local.isoformat(), "node": node})


def placidus_house(lon_s: float, cusps: list) -> int:
    """Which Placidus bhava a longitude falls in. This is Bhav Chalit."""
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        span = (b - a) % 360
        if (lon_s - a) % 360 < span:
            return i + 1
    return 1


def solar_return_jd(natal_sun_sidereal: float, jd_guess: float) -> float:
    """Bisection on the Sun's sidereal longitude. Used for Varshphal."""
    def f(jd):
        xx, _ = swe.calc_ut(jd, swe.SUN, FLAGS)
        return (xx[0] - natal_sun_sidereal + 180) % 360 - 180

    lo, hi = jd_guess - 3, jd_guess + 3
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2
