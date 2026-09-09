"""
Reading a North Indian chart from a photograph.

The North Indian chart is a fixed diagram: a square, both diagonals, and a
rhombus through the side midpoints. The twelve regions never move. House 1 is
always the top centre diamond and the numbering runs anticlockwise. What varies
is only which rashi number sits in each region and which graha abbreviations
are written there.

That means the hard part is not layout inference, it is glyph recognition under
bad lighting, mixed Devanagari and Latin abbreviations, and handwriting. So:
rectify the image to a canonical 400x400 square first, then read it.

Two readers:
  1. Claude Vision on the rectified whole image with a strict JSON schema.
     Better at handwriting and at Devanagari, and it can use chart-wide context
     (rashi numbers must run in an unbroken anticlockwise sequence) to correct a
     single misread digit.
  2. Tesseract per cropped region. Deterministic, offline, cheap. Used as the
     fallback and as a disagreement check.

Never merge the two silently. If they disagree, return both and lower the
confidence so the UI asks the user.
"""
from __future__ import annotations

import base64
import json
import os
import re

import cv2
import numpy as np

# Canonical region polygons on a 400x400 rectified chart, house 1 first.
HOUSE_POLYGONS = [
    [(200, 0), (300, 100), (200, 200), (100, 100)],     # 1  top centre diamond
    [(0, 0), (200, 0), (100, 100)],                     # 2
    [(0, 0), (100, 100), (0, 200)],                     # 3
    [(0, 200), (100, 100), (200, 200), (100, 300)],     # 4  left diamond
    [(0, 200), (100, 300), (0, 400)],                   # 5
    [(0, 400), (100, 300), (200, 400)],                 # 6
    [(200, 200), (300, 300), (200, 400), (100, 300)],   # 7  bottom diamond
    [(200, 400), (300, 300), (400, 400)],               # 8
    [(400, 400), (300, 300), (400, 200)],               # 9
    [(200, 200), (300, 100), (400, 200), (300, 300)],   # 10 right diamond
    [(400, 200), (300, 100), (400, 0)],                 # 11
    [(400, 0), (200, 0), (300, 100)],                   # 12
]

PLANET_ALIASES = {
    "SU": "Su", "SY": "Su", "SUN": "Su", "SURYA": "Su", "रवि": "Su", "सू": "Su",
    "MO": "Mo", "MOON": "Mo", "CH": "Mo", "CHA": "Mo", "चं": "Mo", "चन्द्र": "Mo",
    "MA": "Ma", "MARS": "Ma", "MAN": "Ma", "KU": "Ma", "मं": "Ma", "मंगल": "Ma",
    "ME": "Me", "MER": "Me", "BU": "Me", "बु": "Me", "बुध": "Me",
    "JU": "Ju", "JUP": "Ju", "GU": "Ju", "BR": "Ju", "गु": "Ju", "गुरु": "Ju",
    "VE": "Ve", "VEN": "Ve", "SK": "Ve", "SU_K": "Ve", "शु": "Ve", "शुक्र": "Ve",
    "SA": "Sa", "SAT": "Sa", "SHA": "Sa", "श": "Sa", "शनि": "Sa",
    "RA": "Ra", "RAH": "Ra", "रा": "Ra", "राहु": "Ra",
    "KE": "Ke", "KET": "Ke", "के": "Ke", "केतु": "Ke",
    "AS": "As", "ASC": "As", "LG": "As", "लग्न": "As",
}

VISION_PROMPT = """You are reading a North Indian (diamond) Vedic birth chart.

Layout facts you must assume:
- The chart is a square with both diagonals and a rhombus through the side midpoints, giving 12 regions.
- House 1 is the top centre diamond. Numbering proceeds ANTICLOCKWISE: 2 is the upper-left triangle, 3 the left-upper triangle, 4 the left diamond, and so on.
- In each region there is exactly one small number from 1 to 12. That number is the RASHI (1 = Aries through 12 = Pisces), NOT the house number.
- Rashi numbers always run in an unbroken anticlockwise sequence, wrapping 12 to 1. Use this to correct any single digit you are unsure of.
- Planet abbreviations are written inside the region. They may be Latin (Su, Mo, Ma, Me, Ju, Ve, Sa, Ra, Ke, As/Lg) or Devanagari. A trailing (R), superscript R, or a small mark indicates retrograde. Degrees may appear next to a planet.

Return ONLY valid JSON, no prose, no markdown fence:
{
  "lagna_sign": <1-12, the rashi number in house 1>,
  "houses": [
    {"house": 1, "rashi": <1-12>, "planets": [{"code": "Ju", "retrograde": false, "degree": 12.5}]},
    ... all 12, in order ...
  ],
  "ambiguities": ["short note per uncertain glyph, empty list if none"],
  "confidence": <0.0-1.0>
}

Rules:
- Use the two-letter codes Su Mo Ma Me Ju Ve Sa Ra Ke and As for the ascendant marker.
- Omit "degree" entirely if no degree is printed. Never invent one.
- If a glyph could be two planets, pick the likelier one AND add a note to ambiguities.
- If you cannot read a region at all, give it "planets": [] and note it. Do not guess."""


# ------------------------------------------------------------- rectification

def rectify(image_bytes: bytes, size: int = 400) -> np.ndarray:
    """Find the chart's outer square and warp it to a size x size canvas."""
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Not a decodable image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    img_area = img.shape[0] * img.shape[1]
    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.20 * img_area:
            best = approx.reshape(4, 2).astype("float32")
            break

    if best is None:
        # No square found. Assume the upload is already cropped to the chart.
        return cv2.resize(img, (size, size))

    s = best.sum(axis=1)
    d = np.diff(best, axis=1).ravel()
    ordered = np.array([best[np.argmin(s)], best[np.argmin(d)],
                        best[np.argmax(s)], best[np.argmax(d)]], dtype="float32")
    dst = np.array([[0, 0], [size, 0], [size, size], [0, size]], dtype="float32")
    M = cv2.getPerspectiveTransform(ordered, dst)
    return cv2.warpPerspective(img, M, (size, size))


def crop_house(canvas: np.ndarray, house: int, pad: int = 4) -> np.ndarray:
    mask = np.zeros(canvas.shape[:2], np.uint8)
    poly = np.array(HOUSE_POLYGONS[house - 1], np.int32)
    cv2.fillPoly(mask, [poly], 255)
    mask = cv2.erode(mask, np.ones((pad, pad), np.uint8))
    out = cv2.bitwise_and(canvas, canvas, mask=mask)
    out[mask == 0] = 255
    x, y, w, h = cv2.boundingRect(poly)
    return out[y:y + h, x:x + w]


# ------------------------------------------------------------- vision reader

async def read_with_claude(canvas: np.ndarray, client) -> dict:
    ok, buf = cv2.imencode(".png", canvas)
    if not ok:
        raise ValueError("Encoding failed")
    b64 = base64.b64encode(buf.tobytes()).decode()

    msg = await client.messages.create(
        model=os.getenv("VISION_MODEL", "claude-sonnet-4-6"),
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": VISION_PROMPT},
            ],
        }],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(text)


# ---------------------------------------------------------- tesseract reader

def read_with_tesseract(canvas: np.ndarray) -> dict:
    import pytesseract

    houses = []
    for h in range(1, 13):
        crop = crop_house(canvas, h)
        crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        txt = pytesseract.image_to_string(
            th, lang=os.getenv("TESS_LANG", "eng+hin"),
            config="--psm 6 -c tessedit_char_whitelist="
                   "0123456789AaBbCcDdEeGgHhJjKkLlMmNnPpRrSsTtUuVv().")
        nums = [int(n) for n in re.findall(r"\b(1[0-2]|[1-9])\b", txt)]
        codes = []
        for tok in re.findall(r"[A-Za-z\u0900-\u097F]{2,6}", txt):
            code = PLANET_ALIASES.get(tok.upper())
            if code and code not in [p["code"] for p in codes]:
                codes.append({"code": code, "retrograde": "(R)" in txt or "R)" in txt})
        houses.append({"house": h, "rashi": nums[0] if nums else None, "planets": codes})
    return {"houses": houses, "confidence": 0.5, "ambiguities": ["tesseract fallback"]}


# ------------------------------------------------------------- reconciliation

def validate(result: dict) -> dict:
    """
    Structural checks. A North Indian chart that fails these was misread, and
    the right response is to say so rather than to return a plausible chart.
    """
    warnings = []
    houses = {h["house"]: h for h in result.get("houses", [])}

    if set(houses) != set(range(1, 13)):
        warnings.append("Not all twelve houses were read")
        result["confidence"] = min(result.get("confidence", 0.5), 0.3)
        result["warnings"] = warnings
        return result

    rashis = [houses[h].get("rashi") for h in range(1, 13)]
    if any(r is None for r in rashis):
        warnings.append("At least one rashi number is missing")
    else:
        base = rashis[0]
        expected = [((base - 1 + i) % 12) + 1 for i in range(12)]
        if rashis != expected:
            bad = [i + 1 for i in range(12) if rashis[i] != expected[i]]
            if len(bad) == 1:
                # One digit off against eleven agreeing: repair it and say so.
                h = bad[0]
                warnings.append(
                    f"House {h} read as rashi {rashis[h-1]}, corrected to {expected[h-1]} "
                    f"because the anticlockwise sequence is otherwise unbroken")
                houses[h]["rashi"] = expected[h - 1]
            else:
                warnings.append(
                    f"Rashi sequence is not a valid anticlockwise run; houses {bad} disagree. "
                    f"The chart orientation or the crop is probably wrong.")
                result["confidence"] = min(result.get("confidence", 0.5), 0.25)

    seen = {}
    for h in range(1, 13):
        for p in houses[h].get("planets", []):
            seen.setdefault(p["code"], []).append(h)
    for code, where in seen.items():
        if code != "As" and len(where) > 1:
            warnings.append(f"{code} appears in houses {where}; a graha occupies exactly one")
            result["confidence"] = min(result.get("confidence", 0.5), 0.4)

    missing = [p for p in ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa", "Ra", "Ke"] if p not in seen]
    if missing:
        warnings.append(f"Not found in the image: {', '.join(missing)}")

    if "Ra" in seen and "Ke" in seen:
        if (seen["Ra"][0] - seen["Ke"][0]) % 12 != 6:
            warnings.append("Rahu and Ketu are not six houses apart, which is impossible")
            result["confidence"] = min(result.get("confidence", 0.5), 0.25)

    result["lagna_sign"] = houses[1].get("rashi")
    result["houses"] = [houses[h] for h in range(1, 13)]
    result["warnings"] = warnings
    return result


async def read_chart_image(image_bytes: bytes, anthropic_client=None) -> dict:
    canvas = rectify(image_bytes)
    primary, error = None, None
    if anthropic_client is not None:
        try:
            primary = validate(await read_with_claude(canvas, anthropic_client))
        except Exception as exc:
            error = f"vision reader failed: {exc}"

    if primary is None or primary.get("confidence", 0) < 0.55:
        try:
            fallback = validate(read_with_tesseract(canvas))
        except Exception as exc:
            fallback = None
            error = (error or "") + f" tesseract failed: {exc}"
        if primary is None:
            primary = fallback or {"houses": [], "confidence": 0.0,
                                   "warnings": [error or "both readers failed"]}
        elif fallback:
            agree = [a["rashi"] == b["rashi"]
                     for a, b in zip(primary["houses"], fallback["houses"])]
            primary["second_opinion"] = fallback
            primary["agreement"] = round(sum(agree) / 12, 2)

    primary["source"] = "image"
    primary["note"] = ("An image yields houses and signs only. Degrees, nakshatras, "
                       "Vimshottari, Ashtakavarga and every KP routine need a birth time.")
    return primary


def to_partial_chart(read: dict) -> dict:
    """
    Convert a validated image read into the subset of the chart contract that
    degree-free rules can consume. Rules that call deg_in_sign, sub_lord or any
    dasha function must be filtered out before running against this.
    """
    lagna_sign = (read["lagna_sign"] or 1) - 1
    positions = {}
    for h in read["houses"]:
        for p in h.get("planets", []):
            if p["code"] == "As":
                continue
            positions[p["code"]] = {
                "sign": h["rashi"] - 1,
                "house": h["house"],
                "retro": p.get("retrograde", False),
                "deg_in_sign": p.get("degree"),
            }
    return {"lagna_sign": lagna_sign, "positions": positions,
            "degrees_known": all(v["deg_in_sign"] is not None for v in positions.values()),
            "available_rules": "sign_and_house_only"}
