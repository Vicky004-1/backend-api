"""
The prediction engine.

Design note, because this is the part people get wrong. A tree of nested
if/else statements cannot represent a chart. Real charts contradict themselves:
the 7th lord is exalted AND Saturn sits in the 7th AND the Upapada is in the
12th. A first-match tree returns whichever branch the author happened to write
first, and the same chart read in a different order gives a different answer.

So: every astrological statement is a Rule that either fires or does not. A
fired rule contributes a signed weight and a sentence of evidence. A domain
verdict is the aggregate. Nothing in this file returns a prediction directly.

Weights are on a 1-5 scale:
  5  classical yoga with an explicit textual basis and no common exception
  4  strong single-factor rule (KP cuspal sub-lord, dusthana 7th lord)
  3  ordinary supporting factor
  2  modifying factor
  1  colour, not evidence

Confidence is separate from score. Score says which way the evidence points.
Confidence says how much evidence there was. A +80 score from two rules is a
weaker statement than a +40 from eleven.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

BENEFICS = {"Ju", "Ve", "Me", "Mo"}
MALEFICS = {"Su", "Ma", "Sa", "Ra", "Ke"}
KENDRA = {1, 4, 7, 10}
TRIKONA = {1, 5, 9}
DUSTHANA = {6, 8, 12}
UPACHAYA = {3, 6, 10, 11}
MARAKA = {2, 7}


class Ctx:
    """Everything a rule is allowed to ask about a chart."""

    def __init__(self, chart, ashtaka, jaimini, kp_sig, transits=None):
        self.chart = chart
        self.P = chart.positions
        self.L = chart.lagna_sign
        self.ashtaka = ashtaka
        self.jaimini = jaimini
        self.kp = kp_sig
        self.transits = transits or {}

    # --- placement ---------------------------------------------------------
    def house_of(self, p): return self.P[p].house
    def chalit_of(self, p): return self.P[p].chalit
    def sign_of(self, p): return self.P[p].sign
    def sign_of_house(self, h): return (self.L + h - 1) % 12

    def lord_of(self, h):
        from ..core.ephemeris import SIGN_LORD
        return SIGN_LORD[self.sign_of_house(h)]

    def house_of_lord(self, h): return self.house_of(self.lord_of(h))
    def occupants(self, h): return [k for k in self.P if self.house_of(k) == h]

    # --- relationship ------------------------------------------------------
    def conjunct(self, a, b, orb=None):
        if orb is None:
            return self.sign_of(a) == self.sign_of(b)
        sep = abs((self.P[a].lon - self.P[b].lon + 180) % 360 - 180)
        return sep <= orb

    def aspects_of(self, p):
        h = self.house_of(p)
        angles = [7]
        if p == "Ma": angles += [4, 8]
        if p == "Ju": angles += [5, 9]
        if p == "Sa": angles += [3, 10]
        if p in ("Ra", "Ke"): angles += [5, 9]
        return {((h - 1 + a - 1) % 12) + 1 for a in angles}

    def aspects_house(self, p, h): return h in self.aspects_of(p)
    def aspects_planet(self, a, b): return self.house_of(b) in self.aspects_of(a)

    def exchange(self, a, b):
        from ..core.ephemeris import SIGN_LORD
        return SIGN_LORD[self.sign_of(a)] == b and SIGN_LORD[self.sign_of(b)] == a

    # --- strength ----------------------------------------------------------
    def strong(self, p):
        return (self.P[p].dignity in ("Exalted", "Moolatrikona", "Own sign")
                and not self.P[p].combust)

    def weak(self, p):
        return (self.P[p].dignity == "Debilitated" or self.P[p].combust
                or self.house_of(p) in DUSTHANA)

    def afflicted(self, h):
        return any(self.house_of(m) == h or self.aspects_house(m, h) for m in MALEFICS)

    def benefited(self, h):
        return any((self.house_of(b) == h and not self.P[b].combust)
                   or self.aspects_house(b, h) for b in BENEFICS)

    def sav(self, h): return self.ashtaka["sav_by_house"][h - 1]
    def bav(self, p, h): return self.ashtaka["bav"][p][(self.L + h - 1) % 12]

    # --- kp / jaimini ------------------------------------------------------
    def signifies(self, p): return set(self.kp["per_planet"][p])
    def cusp_sub_lord(self, h): return self.kp["cuspal_sub_lords"][h]
    def karaka(self, name): return self.jaimini["karakas"][name]
    def pada(self, n): return self.jaimini["padas"][f"A{n}"]

    def house_from(self, base_sign, target_sign):
        return ((target_sign - base_sign) % 12) + 1

    # --- neecha bhanga, the single most common source of false negatives ----
    def neecha_bhanga(self, p):
        """
        Cancellation of debilitation. Any one of these lifts it:
          - the lord of the debilitation sign is in a kendra from Lagna or Moon
          - the planet exalted in that sign is in a kendra from Lagna or Moon
          - the planet is in a kendra from Lagna and its dispositor is strong
        """
        from ..core.ephemeris import SIGN_LORD, EXALT
        if self.P[p].dignity != "Debilitated":
            return False
        sign = self.sign_of(p)
        disp = SIGN_LORD[sign]
        exalted_here = next((k for k, v in EXALT.items() if v[0] == sign), None)
        moon_h = self.house_of("Mo")
        for cand in filter(None, [disp, exalted_here]):
            if self.house_of(cand) in KENDRA:
                return True
            if ((self.sign_of(cand) - self.sign_of("Mo")) % 12) + 1 in KENDRA:
                return True
        return self.house_of(p) in KENDRA and self.strong(disp)


@dataclass
class Rule:
    id: str
    domain: str
    weight: int
    test: Callable[[Ctx], Optional[dict]]
    tag: str | None = None      # for two-sided questions (job vs business)
    school: str = "parashari"   # parashari | kp | jaimini | tajika


@dataclass
class Hit:
    rule_id: str
    weight: int
    polarity: int
    text: str
    tag: str | None
    school: str


def run(rules: list[Rule], ctx: Ctx) -> dict:
    hits, pos, neg = [], 0, 0
    for r in rules:
        try:
            res = r.test(ctx)
        except (KeyError, IndexError, TypeError):
            continue
        if not res:
            continue
        pol = res.get("polarity", 1)
        w = res.get("weight", r.weight)
        hits.append(Hit(r.id, w, pol, res["text"], r.tag, r.school))
        if pol > 0:
            pos += w
        else:
            neg += w

    total = pos + neg
    score = 0 if total == 0 else round((pos - neg) / total * 100)
    return {
        "score": score,
        "positive_weight": pos,
        "negative_weight": neg,
        "confidence": min(100, total * 6),
        "verdict": verdict(score, total),
        "hits": [h.__dict__ for h in hits],
        "by_school": {s: sum(h.weight * h.polarity for h in hits if h.school == s)
                      for s in {h.school for h in hits}},
    }


def verdict(score: int, total: int) -> str:
    if total < 4:
        return "Insufficient evidence"
    if score >= 55:
        return "Strongly supported"
    if score >= 20:
        return "Supported, with friction"
    if score > -20:
        return "Genuinely mixed"
    if score > -55:
        return "Obstructed"
    return "Heavily obstructed"


def two_sided(rules: list[Rule], ctx: Ctx, tag_a: str, tag_b: str) -> dict:
    a = run([r for r in rules if r.tag == tag_a], ctx)
    b = run([r for r in rules if r.tag == tag_b], ctx)
    lean = a["positive_weight"] - b["positive_weight"]
    if abs(lean) < 3:
        call = "balanced"
    else:
        call = tag_a if lean > 0 else tag_b
    return {"a": a, "b": b, "lean": lean, "call": call}


def cross_check(domain_result: dict, min_schools: int = 2) -> dict:
    """
    A prediction backed only by one school is a hypothesis. Flag it. The house
    style is: state it, and say which school it rests on, rather than dressing
    a single KP rule up as a settled reading.
    """
    schools = domain_result["by_school"]
    agreeing = [s for s, v in schools.items() if v * domain_result["score"] > 0]
    domain_result["corroborated"] = len(agreeing) >= min_schools
    domain_result["resting_on"] = agreeing
    return domain_result
