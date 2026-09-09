"""
Krishnamurti Paddhati layer: sub divisions, the four-fold significator
hierarchy, and cuspal sub-lord judgement.

On the "249 subs": 27 nakshatras x 9 subs = 243 distinct divisions. The printed
KP tables show 249 rows because six subs straddle a sign boundary and get
listed once per sign. This module builds the 243 real divisions; if you are
diffing against a printed table, that is the discrepancy.

The whole system rests on the sub-lord, so this module must be fed Placidus
cusps and a birth time accurate to the minute. A 4-minute error moves the
Ascendant by roughly one degree, which is enough to change the 1st cuspal
sub-lord and invert a verdict.
"""
from __future__ import annotations

from bisect import bisect_right

NAK_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]
ORDER = ["Ke", "Ve", "Su", "Mo", "Ma", "Ra", "Ju", "Sa", "Me"]
YEARS = {"Ke": 7, "Ve": 20, "Su": 6, "Mo": 10, "Ma": 7,
         "Ra": 18, "Ju": 16, "Sa": 19, "Me": 17}
NAK_SPAN = 40 / 3.0  # 13 deg 20 min


def _build_subs():
    """243 divisions: (start_lon, star_lord, sub_lord)."""
    edges, meta = [], []
    start = 0.0
    for n in range(27):
        star = ORDER[n % 9]
        k = ORDER.index(star)
        cur = start
        for j in range(9):
            sub = ORDER[(k + j) % 9]
            edges.append(cur)
            meta.append((star, sub))
            cur += NAK_SPAN * YEARS[sub] / 120.0
        start += NAK_SPAN
    return edges, meta


SUB_EDGES, SUB_META = _build_subs()


def nakshatra_of(lon: float) -> dict:
    idx = int(lon // NAK_SPAN)
    into = lon - idx * NAK_SPAN
    return {
        "index": idx,
        "name": NAK_NAMES[idx],
        "lord": ORDER[idx % 9],
        "pada": int(into // (10 / 3)) + 1,
        "fraction": into / NAK_SPAN,
    }


def sub_lords(lon: float):
    """Returns (star lord, sub lord, sub-sub lord)."""
    i = bisect_right(SUB_EDGES, lon) - 1
    i = max(0, min(i, len(SUB_EDGES) - 1))
    star, sub = SUB_META[i]
    lo = SUB_EDGES[i]
    hi = SUB_EDGES[i + 1] if i + 1 < len(SUB_EDGES) else 360.0
    frac = (lon - lo) / (hi - lo)
    k, acc, subsub = ORDER.index(sub), 0.0, sub
    for j in range(9):
        c = ORDER[(k + j) % 9]
        w = YEARS[c] / 120.0
        if acc <= frac < acc + w:
            subsub = c
            break
        acc += w
    return star, sub, subsub


# ------------------------------------------------------------- significators

def house_of_cusp(lon: float, cusps: list) -> int:
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        if (lon - a) % 360 < (b - a) % 360:
            return i + 1
    return 1


def owned_houses(planet: str, cusps: list) -> list:
    """A planet owns the houses whose cusp falls in a sign it rules."""
    from .ephemeris import SIGN_LORD
    return [i + 1 for i, c in enumerate(cusps) if SIGN_LORD[int(c // 30)] == planet]


def significators(chart) -> dict:
    """
    Four-fold hierarchy, strongest first:
      A  planets in the star of the occupant of the house
      B  the occupant itself
      C  planets in the star of the owner of the house
      D  the owner itself
    Returned per planet as the houses it signifies, plus the house-wise grouping
    KP actually judges on.
    """
    P = chart.positions
    cusps = chart.cusps
    occupants = {h: [] for h in range(1, 13)}
    for k, p in P.items():
        occupants[house_of_cusp(p.lon, cusps)].append(k)

    owners = {k: owned_houses(k, cusps) for k in P}

    per_planet = {}
    for k, p in P.items():
        houses = set()
        star = p.star_lord
        if star in P:
            houses.add(house_of_cusp(P[star].lon, cusps))
            houses.update(owners.get(star, []))
        houses.add(house_of_cusp(p.lon, cusps))
        houses.update(owners.get(k, []))
        # A node signifies for its dispositor and for planets conjoined with it,
        # which is the single most misapplied rule in KP. Handle it explicitly.
        if k in ("Ra", "Ke"):
            from .ephemeris import SIGN_LORD
            disp = SIGN_LORD[p.sign]
            if disp in P:
                houses.add(house_of_cusp(P[disp].lon, cusps))
                houses.update(owners.get(disp, []))
            for other, q in P.items():
                if other not in ("Ra", "Ke") and q.sign == p.sign:
                    houses.add(house_of_cusp(q.lon, cusps))
                    houses.update(owners.get(other, []))
        per_planet[k] = sorted(houses)

    per_house = {h: [] for h in range(1, 13)}
    for h in range(1, 13):
        tiers = {"A": [], "B": [], "C": [], "D": []}
        occ = occupants[h]
        own = [k for k, v in owners.items() if h in v]
        for k, p in P.items():
            if p.star_lord in occ:
                tiers["A"].append(k)
            elif p.star_lord in own:
                tiers["C"].append(k)
        tiers["B"] = occ
        tiers["D"] = own
        per_house[h] = tiers

    return {"per_planet": per_planet, "per_house": per_house,
            "cuspal_sub_lords": {h: sub_lords(cusps[h - 1])[1] for h in range(1, 13)}}


def cusp_promises(chart, house: int, required: set[int]) -> dict:
    """
    KP's central test. The cuspal sub-lord of the house in question must signify
    at least one of the required houses for the matter to be promised at all.
    Marriage: {2, 7, 11}.  Job: {2, 6, 10, 11}.  Own house: {4, 11, 12}.
    Denial set matters too: if the sub-lord signifies only the 6/8/12 of the
    matter, read refusal rather than delay.
    """
    sig = significators(chart)
    sl = sig["cuspal_sub_lords"][house]
    houses = set(sig["per_planet"][sl])
    negatives = {(house + 5 - 1) % 12 + 1, (house + 7 - 1) % 12 + 1, (house + 11 - 1) % 12 + 1}
    return {
        "cusp": house,
        "sub_lord": sl,
        "signifies": sorted(houses),
        "promised": bool(houses & required),
        "denial_flag": bool(houses & negatives) and not (houses & required),
    }


def ruling_planets(chart_now) -> list:
    """
    Ruling planets of the moment: day lord, Moon's sign lord, Moon's star lord,
    Lagna sign lord, Lagna star lord. Used to confirm a timing window rather
    than to generate one.
    """
    from .ephemeris import SIGN_LORD
    P = chart_now.positions
    import swisseph as swe
    weekday = int((chart_now.jd_ut + 1.5) % 7)
    day_lord = ["Su", "Mo", "Ma", "Me", "Ju", "Ve", "Sa"][weekday]
    rp = [
        day_lord,
        SIGN_LORD[P["Mo"].sign],
        P["Mo"].star_lord,
        SIGN_LORD[chart_now.lagna_sign],
        sub_lords(chart_now.lagna)[0],
    ]
    seen, out = set(), []
    for r in rp:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out
