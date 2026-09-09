"""
Vimshottari, Ashtakavarga, Jaimini and Tajika.

Kept in one module because the rule engine consumes all four together and they
share the same sign-arithmetic helpers.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ephemeris import SIGN_LORD, navamsa
from kp import ORDER, YEARS, NAK_SPAN, nakshatra_of

SIDEREAL_YEAR_DAYS = 365.2425  # Vimshottari convention; some schools use 360


# =============================================================== Vimshottari

def vimshottari(moon_lon: float, birth: datetime, levels: int = 3) -> list:
    nak = nakshatra_of(moon_lon)
    lord = nak["lord"]
    elapsed = nak["fraction"]
    start = birth - timedelta(days=elapsed * YEARS[lord] * SIDEREAL_YEAR_DAYS)

    def expand(parent_lord, t0, days, depth):
        k = ORDER.index(parent_lord)
        out, t = [], t0
        for j in range(9):
            L = ORDER[(k + j) % 9]
            d = days * YEARS[L] / 120.0
            node = {"lord": L, "start": t.isoformat(), "end": (t + timedelta(days=d)).isoformat()}
            if depth < levels:
                node["children"] = expand(L, t, d, depth + 1)
            out.append(node)
            t += timedelta(days=d)
        return out

    k = ORDER.index(lord)
    out, t = [], start
    for i in range(9):
        L = ORDER[(k + i) % 9]
        days = YEARS[L] * SIDEREAL_YEAR_DAYS
        node = {"lord": L, "start": t.isoformat(),
                "end": (t + timedelta(days=days)).isoformat(),
                "children": expand(L, t, days, 2)}
        out.append(node)
        t += timedelta(days=days)
    return out


def flatten_periods(tree, path=()):
    for n in tree:
        p = path + (n["lord"],)
        yield {"path": p, "start": n["start"], "end": n["end"]}
        if "children" in n:
            yield from flatten_periods(n["children"], p)


def windows_for(tree, significators: set[str], depth: int = 2, after: datetime | None = None):
    """
    Timing windows: periods where every level of the path is a significator.
    Depth 2 gives mahadasha/antardasha, depth 3 adds the pratyantardasha and is
    what you quote when a client wants a month rather than a year.
    """
    out = []
    for p in flatten_periods(tree):
        if len(p["path"]) != depth:
            continue
        if not set(p["path"]) <= significators:
            continue
        if after and datetime.fromisoformat(p["end"]) < after:
            continue
        out.append(p)
    return out


# ============================================================== Ashtakavarga

BAV_TABLE = {
    "Su": {"Su": [1,2,4,7,8,9,10,11], "Mo": [3,6,10,11], "Ma": [1,2,4,7,8,9,10,11],
           "Me": [3,5,6,9,10,11,12], "Ju": [5,6,9,11], "Ve": [6,7,12],
           "Sa": [1,2,4,7,8,9,10,11], "La": [3,4,6,10,11,12]},
    "Mo": {"Su": [3,6,7,8,10,11], "Mo": [1,3,6,7,10,11], "Ma": [2,3,5,6,9,10,11],
           "Me": [1,3,4,5,7,8,10,11], "Ju": [1,4,7,8,10,11,12], "Ve": [3,4,5,7,9,10,11],
           "Sa": [3,5,6,11], "La": [3,6,10,11]},
    "Ma": {"Su": [3,5,6,10,11], "Mo": [3,6,11], "Ma": [1,2,4,7,8,10,11],
           "Me": [3,5,6,11], "Ju": [6,10,11,12], "Ve": [6,8,11,12],
           "Sa": [1,4,7,8,9,10,11], "La": [1,3,6,10,11]},
    "Me": {"Su": [5,6,9,11,12], "Mo": [2,4,6,8,10,11], "Ma": [1,2,4,7,8,9,10,11],
           "Me": [1,3,5,6,9,10,11,12], "Ju": [6,8,11,12], "Ve": [1,2,3,4,5,8,9,11],
           "Sa": [1,2,4,7,8,9,10,11], "La": [1,2,4,6,8,10,11]},
    "Ju": {"Su": [1,2,3,4,7,8,9,10,11], "Mo": [2,5,7,9,11], "Ma": [1,2,4,7,8,10,11],
           "Me": [1,2,4,5,6,9,10,11], "Ju": [1,2,3,4,7,8,10,11], "Ve": [2,5,6,9,10,11],
           "Sa": [3,5,6,12], "La": [1,2,4,5,6,7,9,10,11]},
    "Ve": {"Su": [8,11,12], "Mo": [1,2,3,4,5,8,9,11,12], "Ma": [3,5,6,9,11,12],
           "Me": [3,5,6,9,11], "Ju": [5,8,9,10,11], "Ve": [1,2,3,4,5,8,9,10,11],
           "Sa": [3,4,5,8,9,10,11], "La": [1,2,3,4,5,8,9,11]},
    "Sa": {"Su": [1,2,4,7,8,10,11], "Mo": [3,6,11], "Ma": [3,5,6,10,11,12],
           "Me": [6,8,9,10,11,12], "Ju": [5,6,11,12], "Ve": [6,11,12],
           "Sa": [3,5,6,11], "La": [1,3,4,6,10,11]},
}
# Fixed row totals: Su 48, Mo 49, Ma 39, Me 54, Ju 56, Ve 52, Sa 39 -> SAV 337.
# These never vary by chart, so assert them at import. A typo in one of the
# 337 entries above shifts every downstream bindu judgement silently, and this
# assertion is the only thing that catches it.
_EXPECTED_TOTALS = {"Su": 48, "Mo": 49, "Ma": 39, "Me": 54, "Ju": 56, "Ve": 52, "Sa": 39}
for _p, _refs in BAV_TABLE.items():
    _t = sum(len(v) for v in _refs.values())
    assert _t == _EXPECTED_TOTALS[_p], f"BAV table for {_p} totals {_t}, expected {_EXPECTED_TOTALS[_p]}"
assert sum(_EXPECTED_TOTALS.values()) == 337


def ashtakavarga(chart) -> dict:
    P = chart.positions
    bav, sav = {}, [0] * 12
    for p, refs in BAV_TABLE.items():
        row = [0] * 12
        for ref, places in refs.items():
            base = chart.lagna_sign if ref == "La" else P[ref].sign
            for h in places:
                row[(base + h - 1) % 12] += 1
        bav[p] = row
        for i, v in enumerate(row):
            sav[i] += v
    return {"bav": bav, "sav": sav,
            "sav_by_house": [sav[(chart.lagna_sign + h - 1) % 12] for h in range(1, 13)]}


def trikona_shodhana(bav_row: list) -> list:
    """
    Trikona reduction: within each trine group take the lowest value and
    subtract. Needed before Shodhya Pinda, not before ordinary bindu reading.
    """
    out = bav_row[:]
    for start in range(4):
        group = [start, start + 4, start + 8]
        vals = [out[g] for g in group]
        if 0 in vals:
            lo = 0
        else:
            lo = min(vals)
        for g in group:
            out[g] = out[g] - lo if out[g] != 0 else 0
    return out


# =================================================================== Jaimini

KARAKAS = ["Atmakaraka", "Amatyakaraka", "Bhratrikaraka", "Matrikaraka",
           "Putrakaraka", "Gnatikaraka", "Darakaraka"]


def chara_karakas(chart, scheme: int = 7) -> dict:
    """
    Rank by degrees traversed in the sign, descending. In the 8-karaka scheme
    Rahu joins with 30 minus its degree, because it moves backwards.
    """
    P = chart.positions
    rows = [(k, P[k].deg_in_sign) for k in ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa"]]
    if scheme == 8:
        rows.append(("Ra", 30 - P["Ra"].deg_in_sign))
    rows.sort(key=lambda r: -r[1])
    names = KARAKAS if scheme == 7 else KARAKAS[:5] + ["Pitrikaraka"] + KARAKAS[5:]
    return {names[i]: rows[i][0] for i in range(min(len(names), len(rows)))}


def arudha(house: int, chart) -> int:
    """
    Count from the house to its lord, then the same count forward from the lord.
    If the result is the house itself or the 7th from it, take the 10th from
    there, because a pada cannot coincide with its own source.
    """
    house_sign = (chart.lagna_sign + house - 1) % 12
    lord = SIGN_LORD[house_sign]
    lord_sign = chart.positions[lord].sign
    dist = ((lord_sign - house_sign) % 12) + 1
    a = (lord_sign + dist - 1) % 12
    if a == house_sign or (a - house_sign) % 12 == 6:
        a = (a + 9) % 12
    return a


def jaimini_block(chart) -> dict:
    ak = chara_karakas(chart)["Atmakaraka"]
    padas = {f"A{h}": arudha(h, chart) for h in range(1, 13)}
    return {
        "karakas": chara_karakas(chart),
        "karakamsha": navamsa(chart.positions[ak].lon),
        "arudha_lagna": padas["A1"],
        "upapada": padas["A12"],
        "padas": padas,
        # 2nd from Upapada carries the durability of the marriage
        "second_from_upapada": (padas["A12"] + 1) % 12,
    }


def chara_dasha(chart, years: int = 100) -> list:
    """
    Chara dasha, Parashara/Jaimini as taught by Rao. Direction is zodiacal when
    the Lagna sign is odd-footed, reverse when even-footed. Duration is the
    count from the sign to its lord minus one, with 12 substituted for 0.
    """
    lagna = chart.lagna_sign
    odd_footed = lagna in (0, 1, 2, 6, 7, 8)
    seq = [(lagna + i) % 12 for i in range(12)] if odd_footed else [(lagna - i) % 12 for i in range(12)]
    out, elapsed = [], 0
    for s in seq:
        lord = SIGN_LORD[s]
        lord_sign = chart.positions[lord].sign
        if s in (0, 1, 2, 6, 7, 8):
            n = ((lord_sign - s) % 12)
        else:
            n = ((s - lord_sign) % 12)
        dur = n if n else 12
        if lord_sign == s:
            dur = 12
        out.append({"sign": s, "years": dur, "from_year": elapsed, "to_year": elapsed + dur})
        elapsed += dur
        if elapsed >= years:
            break
    return out


# ==================================================================== Tajika

DEEPTAMSHA = {"Su": 15, "Mo": 12, "Ma": 8, "Me": 7, "Ju": 9, "Ve": 7, "Sa": 9,
              "Ra": 5, "Ke": 5}


def muntha(lagna_sign: int, age: int) -> int:
    return (lagna_sign + age) % 12


def tajika_aspects(annual_chart) -> list:
    """
    Tajika judges by orb, not by whole sign. Two planets are in aspect when the
    difference from an exact aspect angle is inside the half-sum of their
    deeptamsha. Applying is Ithasala (the matter completes), separating is
    Ishrafa (the matter has passed or fails).
    """
    P = annual_chart.positions
    angles = {0: "Conjunction", 60: "Sextile", 90: "Square", 120: "Trine", 180: "Opposition"}
    keys = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa"]
    out = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            sep = abs((P[a].lon - P[b].lon + 180) % 360 - 180)
            orb_allowed = (DEEPTAMSHA[a] + DEEPTAMSHA[b]) / 2
            for ang, name in angles.items():
                diff = abs(sep - ang)
                if diff <= orb_allowed:
                    faster, slower = (a, b) if abs(P[a].speed) > abs(P[b].speed) else (b, a)
                    behind = (P[faster].lon - P[slower].lon) % 360
                    applying = behind > 180 if P[faster].speed > 0 else behind < 180
                    out.append({
                        "a": a, "b": b, "aspect": name, "orb": round(diff, 2),
                        "allowed": orb_allowed,
                        "type": "Ithasala" if applying else "Ishrafa",
                        "faster": faster,
                        "strength": round(1 - diff / orb_allowed, 3),
                    })
    return out


def kambool(aspects: list, annual_chart) -> list:
    """
    Kambool: an Ithasala between two planets that a third planet, itself in
    Ithasala with the faster of the pair, carries to completion. This is the
    Tajika answer to 'the deal was agreed but did it close'.
    """
    out = []
    ith = [a for a in aspects if a["type"] == "Ithasala"]
    for a in ith:
        for b in ith:
            if b is a:
                continue
            if b["faster"] == a["faster"] and {b["a"], b["b"]} != {a["a"], a["b"]}:
                third = b["a"] if b["b"] == a["faster"] else b["b"]
                out.append({**a, "completed_by": third})
    return out


def year_lord(annual_chart, natal_chart, age: int) -> dict:
    """
    Panchadhikari, five offices. Whichever candidate is strongest becomes the
    Varshesh and colours the whole year.
    """
    m = muntha(natal_chart.lagna_sign, age)
    candidates = {
        "Muntha lord": SIGN_LORD[m],
        "Varsha Lagna lord": SIGN_LORD[annual_chart.lagna_sign],
        "Janma Lagna lord": SIGN_LORD[natal_chart.lagna_sign],
        "Trirashi lord": SIGN_LORD[(annual_chart.lagna_sign // 3) * 3],
        "Dinratri lord": SIGN_LORD[annual_chart.positions["Su"].sign],
    }
    P = annual_chart.positions
    scores = {}
    for office, pl in candidates.items():
        s = 0
        if P[pl].house in (1, 4, 5, 7, 9, 10):
            s += 3
        if P[pl].dignity in ("Exalted", "Moolatrikona", "Own sign"):
            s += 3
        if P[pl].combust:
            s -= 2
        if P[pl].house in (6, 8, 12):
            s -= 2
        scores[office] = (pl, s)
    winner = max(scores.items(), key=lambda kv: kv[1][1])
    return {"muntha_sign": m,
            "muntha_house": ((m - natal_chart.lagna_sign) % 12) + 1,
            "candidates": scores,
            "varshesh": winner[1][0], "office": winner[0]}


def sahams(annual_chart, day_birth: bool = True) -> dict:
    """Tajika sensitive points. Formula flips between day and night birth."""
    P = annual_chart.positions
    L = annual_chart.lagna

    def s(a, b, c):
        v = (a - b + c) % 360
        return v

    out = {
        "Punya": s(P["Mo"].lon, P["Su"].lon, L) if day_birth else s(P["Su"].lon, P["Mo"].lon, L),
        "Vidya": s(P["Su"].lon, P["Mo"].lon, L) if day_birth else s(P["Mo"].lon, P["Su"].lon, L),
        "Vivaha": s(P["Ve"].lon, P["Sa"].lon, L) if day_birth else s(P["Sa"].lon, P["Ve"].lon, L),
        "Karma": s(P["Ma"].lon, P["Su"].lon, L),
        "Roga": s(L, P["Mo"].lon, L),
        "Yasas": s(P["Ju"].lon, P["Su"].lon, L) if day_birth else s(P["Su"].lon, P["Ju"].lon, L),
    }
    return {k: {"lon": round(v, 3), "sign": int(v // 30),
                "house": ((int(v // 30) - annual_chart.lagna_sign) % 12) + 1}
            for k, v in out.items()}
