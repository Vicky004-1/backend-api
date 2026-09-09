"""
The rule catalogue. This is the astrology; everything else is plumbing.

Each rule returns None or {"text": ..., "polarity": +1/-1, "weight": optional}.
Weights follow the scale documented in engine.py. Rules are grouped by domain
and tagged with the school they come from so the output can say what it rests
on.
"""
from __future__ import annotations

from engine import Rule, Ctx, DUSTHANA, KENDRA, TRIKONA, MALEFICS

PN = {"Su": "Sun", "Mo": "Moon", "Ma": "Mars", "Me": "Mercury", "Ju": "Jupiter",
      "Ve": "Venus", "Sa": "Saturn", "Ra": "Rahu", "Ke": "Ketu"}
SG = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra",
      "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


def R(id, domain, weight, fn, tag=None, school="parashari"):
    return Rule(id=id, domain=domain, weight=weight, test=fn, tag=tag, school=school)


def yes(text, polarity=1, weight=None):
    d = {"text": text, "polarity": polarity}
    if weight:
        d["weight"] = weight
    return d


# ==================================================================== CAREER

CAREER = [
    R("car.10l.kendra", "career", 4, lambda c:
      c.house_of_lord(10) in (KENDRA | TRIKONA) and
      yes(f"10th lord {PN[c.lord_of(10)]} occupies house {c.house_of_lord(10)}, a kendra or "
          f"trikona. The career line has structural support and does not depend on luck.")),

    R("car.10l.dusthana", "career", 4, lambda c:
      c.house_of_lord(10) in DUSTHANA and
      yes(f"10th lord {PN[c.lord_of(10)]} falls in house {c.house_of_lord(10)}. Recognition lags "
          f"effort; expect lateral moves, restarts, and work that is real but invisible.", -1)),

    R("car.dkyoga", "career", 5, lambda c:
      c.conjunct(c.lord_of(9), c.lord_of(10)) and
      yes("Dharma-karmadhipati yoga: the 9th and 10th lords are conjoined. This is the single "
          "strongest career combination in Parashari and it outranks most contrary indications.")),

    R("car.10l.exchange.1l", "career", 4, lambda c:
      c.exchange(c.lord_of(1), c.lord_of(10)) and
      yes("Parivartana between the Lagna lord and the 10th lord. The work is an extension of the "
          "person rather than a job held at arm's length; they will not tolerate anonymous roles.")),

    R("car.10l.strong", "career", 3, lambda c:
      c.strong(c.lord_of(10)) and
      yes(f"10th lord {PN[c.lord_of(10)]} is {c.P[c.lord_of(10)].dignity}. Status once earned is kept.")),

    R("car.10l.combust", "career", 3, lambda c:
      c.P[c.lord_of(10)].combust and
      yes(f"10th lord {PN[c.lord_of(10)]} is combust. Credit for the work is routinely absorbed by "
          f"someone senior. Advancement needs a deliberate visibility strategy.", -1)),

    R("car.10l.retro", "career", 2, lambda c:
      c.P[c.lord_of(10)].retro and c.lord_of(10) not in ("Ra", "Ke") and
      yes(f"10th lord {PN[c.lord_of(10)]} is retrograde. Careers here loop: returns to old "
          f"employers, unfinished qualifications resumed, a field abandoned and re-entered.", -1)),

    R("car.sav10", "career", 3, lambda c:
      c.sav(10) >= 32 and yes(f"Sarvashtakavarga gives the 10th house {c.sav(10)} bindus. "
                              f"The profession sector carries real fuel.")),

    R("car.sav10.low", "career", 3, lambda c:
      c.sav(10) <= 25 and yes(f"Only {c.sav(10)} SAV bindus in the 10th. Output stays high relative "
                              f"to reward; the person should optimise for leverage, not effort.", -1)),

    R("car.sav11", "career", 3, lambda c:
      c.sav(11) >= 32 and yes(f"11th house at {c.sav(11)} SAV bindus. Gains and network convert well; "
                              f"income will outpace designation.")),

    R("car.sat.10", "career", 2, lambda c:
      "Sa" in c.occupants(10) and
      yes("Saturn occupies the 10th, where it has digbala. Slow, structural, long-tenure work that "
          "compounds. Early career reads as failure and is not."), tag="job"),

    R("car.sun.10", "career", 2, lambda c:
      "Su" in c.occupants(10) and
      yes("Sun in the 10th: authority, hierarchy, government, or any role with a visible chair."),
      tag="job"),

    R("car.sat.aspect10", "career", 2, lambda c:
      c.aspects_house("Sa", 10) and "Sa" not in c.occupants(10) and
      yes("Saturn aspects the 10th. Promotion arrives late and only after endurance has been "
          "publicly demonstrated. It does arrive.", -1)),

    R("car.amk.good", "career", 3, lambda c:
      c.house_of(c.karaka("Amatyakaraka")) in {1, 2, 5, 9, 10, 11} and
      yes(f"Amatyakaraka {PN[c.karaka('Amatyakaraka')]} sits in house "
          f"{c.house_of(c.karaka('Amatyakaraka'))}. Jaimini's career karaka corroborates the D1."),
      school="jaimini"),

    R("car.amk.bad", "career", 3, lambda c:
      c.house_of(c.karaka("Amatyakaraka")) in DUSTHANA and
      yes(f"Amatyakaraka {PN[c.karaka('Amatyakaraka')]} in house "
          f"{c.house_of(c.karaka('Amatyakaraka'))}. The career theme keeps routing through crisis, "
          f"service, or foreign ground rather than through clean advancement.", -1),
      school="jaimini"),

    R("car.a10", "career", 3, lambda c:
      c.house_from(c.L, c.pada(10)) in (KENDRA | TRIKONA | {11}) and
      yes(f"A10, the career pada, falls in {SG[c.pada(10)]} — house {c.house_from(c.L, c.pada(10))} "
          f"from Lagna. Public perception of the career is better than its private reality, which "
          f"is exactly what a pada measures."), school="jaimini"),

    R("car.kp.10cusp", "career", 4, lambda c:
      bool(c.signifies(c.cusp_sub_lord(10)) & {2, 6, 10, 11}) and
      yes(f"KP: the 10th cuspal sub-lord is {PN[c.cusp_sub_lord(10)]}, signifying houses "
          f"{sorted(c.signifies(c.cusp_sub_lord(10)))}. Professional advancement is promised."),
      school="kp"),

    R("car.kp.10cusp.deny", "career", 4, lambda c:
      not (c.signifies(c.cusp_sub_lord(10)) & {2, 6, 10, 11}) and
      bool(c.signifies(c.cusp_sub_lord(10)) & {5, 9, 12}) and
      yes(f"KP: 10th cuspal sub-lord {PN[c.cusp_sub_lord(10)]} signifies "
          f"{sorted(c.signifies(c.cusp_sub_lord(10)))} without touching 2, 6, 10 or 11. Advancement "
          f"in the current line is refused rather than delayed. Verify the birth time first.", -1),
      school="kp"),
]

# ------------------------------------------------------------ job vs business

JOB_BUSINESS = [
    R("jb.6h.occupied", "jobbiz", 3, lambda c:
      c.occupants(6) and yes(f"{', '.join(PN[p] for p in c.occupants(6))} in the 6th. The service "
                             f"house is live: employment comes easily and suits."), tag="job"),
    R("jb.6l.placed", "jobbiz", 3, lambda c:
      c.house_of_lord(6) in (KENDRA | TRIKONA | {11}) and
      yes(f"6th lord well placed in house {c.house_of_lord(6)}."), tag="job"),
    R("jb.10l.saturnine", "jobbiz", 2, lambda c:
      c.lord_of(10) in ("Sa", "Su") and
      yes(f"10th lord is {PN[c.lord_of(10)]}, a hierarchy planet."), tag="job"),
    R("jb.fixed10", "jobbiz", 2, lambda c:
      c.sign_of_house(10) % 3 == 1 and
      yes("The 10th falls in a fixed sign. Long tenures, not churn."), tag="job"),
    R("jb.kp.6", "jobbiz", 3, lambda c:
      bool(c.signifies(c.cusp_sub_lord(10)) & {6}) and
      yes("KP: the 10th cuspal sub-lord signifies the 6th, the employment house."),
      tag="job", school="kp"),

    R("jb.7l.strong", "jobbiz", 3, lambda c:
      c.strong(c.lord_of(7)) and
      yes(f"7th lord {PN[c.lord_of(7)]} is {c.P[c.lord_of(7)].dignity}. Market-facing trade and "
          f"partnership are supported."), tag="biz"),
    R("jb.7l.10l", "jobbiz", 4, lambda c:
      c.conjunct(c.lord_of(7), c.lord_of(10)) and
      yes("7th and 10th lords conjoined. The classical business-over-service signature."), tag="biz"),
    R("jb.trader.7", "jobbiz", 2, lambda c:
      [p for p in c.occupants(7) if p in ("Me", "Ve", "Ra", "Ma")] and
      yes(f"{', '.join(PN[p] for p in c.occupants(7) if p in ('Me','Ve','Ra','Ma'))} in the 7th. "
          f"Trade instinct."), tag="biz"),
    R("jb.rahu.upachaya", "jobbiz", 2, lambda c:
      c.house_of("Ra") in {3, 7, 10, 11} and
      yes(f"Rahu in house {c.house_of('Ra')}. Appetite for scale and risk that salaried structure "
          f"will frustrate."), tag="biz"),
    R("jb.3.11", "jobbiz", 3, lambda c:
      c.conjunct(c.lord_of(3), c.lord_of(11)) and
      yes("3rd and 11th lords linked: initiative converts directly into gain, which is what an "
          "independent operator needs and an employee cannot use."), tag="biz"),
    R("jb.movable10", "jobbiz", 2, lambda c:
      c.sign_of_house(10) % 3 == 0 and
      yes("Movable 10th. Restless; several ventures rather than one."), tag="biz"),
]

# ================================================================== MARRIAGE

MARRIAGE = [
    R("mar.kp.promise", "marriage", 5, lambda c:
      bool(c.signifies(c.cusp_sub_lord(7)) & {2, 7, 11}) and
      yes(f"KP: the 7th cuspal sub-lord is {PN[c.cusp_sub_lord(7)]}, signifying "
          f"{sorted(c.signifies(c.cusp_sub_lord(7)))}. Marriage is promised — 2, 7 or 11 is present."),
      school="kp"),

    R("mar.kp.deny", "marriage", 5, lambda c:
      not (c.signifies(c.cusp_sub_lord(7)) & {2, 7, 11}) and
      bool(c.signifies(c.cusp_sub_lord(7)) & {1, 6, 10}) and
      yes(f"KP: 7th cuspal sub-lord {PN[c.cusp_sub_lord(7)]} signifies "
          f"{sorted(c.signifies(c.cusp_sub_lord(7)))} — 1, 6 or 10 without 2, 7 or 11. Denial or "
          f"indefinite postponement. Do not deliver this without a rectified birth time.", -1),
      school="kp"),

    R("mar.7l.clean", "marriage", 3, lambda c:
      c.house_of_lord(7) not in DUSTHANA and
      yes(f"7th lord {PN[c.lord_of(7)]} in house {c.house_of_lord(7)}. Clean placement; timing "
          f"follows its own dasha.")),

    R("mar.7l.dusthana", "marriage", 4, lambda c:
      c.house_of_lord(7) in DUSTHANA and
      yes(f"7th lord {PN[c.lord_of(7)]} in house {c.house_of_lord(7)}. The standard delay and "
          f"friction placement.", -1)),

    R("mar.saturn.7", "marriage", 3, lambda c:
      "Sa" in c.occupants(7) and
      yes("Saturn occupies the 7th. Marriage typically after Saturn's maturity around 36, and the "
          "partner tends to be older, graver, or from a more constrained background.", -1)),

    R("mar.mars.7", "marriage", 3, lambda c:
      "Ma" in c.occupants(7) and
      yes("Mars in the 7th, Kuja dosha by house. Friction and haste. Check the partner's chart for "
          "a matching Mars before treating it as a serious obstacle; it cancels against itself.", -1)),

    R("mar.nodes.17", "marriage", 3, lambda c:
      c.house_of("Ra") in (1, 7) and
      yes("The nodal axis lies across 1-7. An unconventional match, or one entered under a "
          "projection that later corrects. Not a bar to marriage, a bar to illusions about it.", -1)),

    R("mar.venus.weak", "marriage", 3, lambda c:
      c.weak("Ve") and not c.neecha_bhanga("Ve") and
      yes(f"Venus is weak ({c.P['Ve'].dignity}"
          f"{', combust' if c.P['Ve'].combust else ''}). The natural karaka of marriage is "
          f"under-supplied.", -1)),

    R("mar.venus.nbry", "marriage", 3, lambda c:
      c.neecha_bhanga("Ve") and
      yes("Venus is debilitated but the debilitation is cancelled. Read this as a difficult start "
          "that resolves, not as damage. Skipping neecha bhanga is the commonest false negative "
          "in automated marriage reading.")),

    R("mar.upapada.good", "marriage", 3, lambda c:
      c.house_from(c.L, c.jaimini["upapada"]) not in DUSTHANA and
      yes(f"Upapada Lagna in {SG[c.jaimini['upapada']]}, house "
          f"{c.house_from(c.L, c.jaimini['upapada'])}. A supported marriage line."), school="jaimini"),

    R("mar.upapada.bad", "marriage", 4, lambda c:
      c.house_from(c.L, c.jaimini["upapada"]) in DUSTHANA and
      yes(f"Upapada Lagna in {SG[c.jaimini['upapada']]}, house "
          f"{c.house_from(c.L, c.jaimini['upapada'])}. Jaimini reads a strained or postponed "
          f"marriage line.", -1), school="jaimini"),

    R("mar.sav7", "marriage", 2, lambda c:
      c.sav(7) >= 30 and yes(f"7th house SAV {c.sav(7)}. Enough strength to sustain a union.")),
    R("mar.sav7.low", "marriage", 2, lambda c:
      c.sav(7) <= 25 and yes(f"7th house SAV only {c.sav(7)}. Thin support for partnership.", -1)),

    R("mar.jup.7", "marriage", 3, lambda c:
      c.aspects_house("Ju", 7) and
      yes("Jupiter aspects the 7th. The classical protection: this alone rescues a badly afflicted "
          "7th more often than any other single factor.")),
]

DIVORCE = [
    R("div.2ndfromUL", "divorce", 5, lambda c:
      [p for p in c.P if c.sign_of(p) == c.jaimini["second_from_upapada"] and p in MALEFICS] and
      yes(f"Malefics "
          f"({', '.join(PN[p] for p in c.P if c.sign_of(p) == c.jaimini['second_from_upapada'] and p in MALEFICS)}) "
          f"in the 2nd from Upapada ({SG[c.jaimini['second_from_upapada']]}). Jaimini's principal "
          f"indicator that the marriage breaks or is endured under permanent strain.", -1),
      school="jaimini"),

    R("div.2ndfromUL.clean", "divorce", 4, lambda c:
      not [p for p in c.P if c.sign_of(p) == c.jaimini["second_from_upapada"]] and
      c.strong(c.lord_of(c.house_from(c.L, c.jaimini["second_from_upapada"]))) and
      yes("The 2nd from Upapada is unoccupied and its lord is dignified. Durability is good."),
      school="jaimini"),

    R("div.6l.7l", "divorce", 4, lambda c:
      c.conjunct(c.lord_of(6), c.lord_of(7)) and
      yes("6th and 7th lords conjoined. Litigation, separation, or a long partner-as-adversary "
          "pattern that does not necessarily end in divorce but reliably ends in lawyers.", -1)),

    R("div.7l.8", "divorce", 4, lambda c:
      c.house_of_lord(7) == 8 and
      yes("7th lord in the 8th. Chronic instability, secrets, and a question mark over the "
          "longevity of the partnership itself.", -1)),

    R("div.ketu.7", "divorce", 3, lambda c:
      "Ke" in c.occupants(7) and
      yes("Ketu in the 7th: the present-but-absent spouse. Detachment rather than conflict, which "
          "is harder to name and harder to fix.", -1)),

    R("div.ma.ra.7", "divorce", 4, lambda c:
      "Ma" in c.occupants(7) and "Ra" in c.occupants(7) and
      yes("Mars and Rahu together in the 7th. The sharpest rupture combination in the catalogue.", -1)),

    R("div.ve.sa", "divorce", 2, lambda c:
      c.conjunct("Ve", "Sa") and
      yes("Venus with Saturn. Affection delivered as duty and received as coldness.", -1)),

    R("div.protection", "divorce", 3, lambda c:
      c.strong(c.lord_of(7)) and c.benefited(7) and
      yes("7th lord dignified and the 7th receives benefic aspect. Real holding power; this "
          "outweighs one or two affliction rules on its own.")),
]

# ------------------------------------------------------------- love/arranged

LOVE = [
    R("lov.5l.7l", "love", 4, lambda c:
      c.conjunct(c.lord_of(5), c.lord_of(7)) and
      yes("5th and 7th lords conjoined. Romance converts into marriage."), tag="love"),
    R("lov.5.7.exchange", "love", 4, lambda c:
      c.exchange(c.lord_of(5), c.lord_of(7)) and
      yes("Parivartana between the 5th and 7th lords. A strong love-marriage signature."), tag="love"),
    R("lov.venus.5", "love", 2, lambda c:
      "Ve" in c.occupants(5) and yes("Venus in the 5th. Romance is a primary channel."), tag="love"),
    R("lov.ve.ma", "love", 2, lambda c:
      c.conjunct("Ve", "Ma", orb=10) and
      yes("Venus and Mars within 10 degrees. Physical attraction drives partner selection."), tag="love"),
    R("lov.rahu.5.7", "love", 3, lambda c:
      c.house_of("Ra") in (5, 7) and
      yes(f"Rahu in house {c.house_of('Ra')}. Attraction across community, language, caste or age "
          f"lines; family resistance is part of the story."), tag="love"),
    R("lov.5.11", "love", 2, lambda c:
      c.conjunct(c.lord_of(5), c.lord_of(11)) and
      yes("5th and 11th lords linked. The romance starts inside the friend circle."), tag="love"),

    R("arr.7l.9l", "love", 4, lambda c:
      c.conjunct(c.lord_of(7), c.lord_of(9)) and
      yes("7th and 9th lords linked. Family and elders steer the match."), tag="arranged"),
    R("arr.jup.7", "love", 2, lambda c:
      c.strong("Ju") and c.aspects_house("Ju", 7) and
      yes("Strong Jupiter aspecting the 7th. A conventional, sanctioned union."), tag="arranged"),
    R("arr.5.empty", "love", 2, lambda c:
      not c.occupants(5) and not c.benefited(5) and
      yes("The 5th is empty and unaspected by benefics. Little romantic momentum of its own."),
      tag="arranged"),
    R("arr.sat.5", "love", 2, lambda c:
      "Sa" in c.occupants(5) and
      yes("Saturn in the 5th inhibits romance. The practical route usually wins."), tag="arranged"),
]

# ==================================================================== WEALTH

WEALTH = [
    R("wl.2.11", "wealth", 5, lambda c:
      c.conjunct(c.lord_of(2), c.lord_of(11)) and
      yes("2nd and 11th lords conjoined. A primary dhana yoga.")),
    R("wl.5.9", "wealth", 5, lambda c:
      c.conjunct(c.lord_of(5), c.lord_of(9)) and
      yes("5th and 9th lords conjoined. The Lakshmi-class trikona yoga: wealth arrives with less "
          "friction than the person's effort would predict.")),
    R("wl.1.2", "wealth", 3, lambda c:
      c.conjunct(c.lord_of(1), c.lord_of(2)) and yes("Lagna lord with the 2nd lord: self-made wealth.")),
    R("wl.1.11", "wealth", 3, lambda c:
      c.conjunct(c.lord_of(1), c.lord_of(11)) and yes("Lagna lord with the 11th lord: gains track effort.")),
    R("wl.chandramangala", "wealth", 3, lambda c:
      c.conjunct("Mo", "Ma") and
      yes("Chandra-Mangala yoga. Commercial gain, characteristically through property or trade "
          "rather than salary.")),
    R("wl.gajakesari", "wealth", 3, lambda c:
      ((c.house_of("Ju") - c.house_of("Mo")) % 12) + 1 in KENDRA and
      yes("Gajakesari yoga: Jupiter in a kendra from the Moon. Reputation converts into resources.")),
    R("wl.11l.dusthana", "wealth", 3, lambda c:
      c.house_of_lord(11) in DUSTHANA and
      yes(f"11th lord in house {c.house_of_lord(11)}. Income leaks as fast as it arrives.", -1)),
    R("wl.2l.12", "wealth", 3, lambda c:
      c.house_of_lord(2) == 12 and
      yes("2nd lord in the 12th. Savings drain into expenditure, travel, or obligation to others.", -1)),
    R("wl.sav", "wealth", 3, lambda c:
      c.sav(2) >= 30 and c.sav(11) >= 30 and
      yes(f"SAV: 2nd house {c.sav(2)}, 11th house {c.sav(11)}. Both wealth houses are fuelled.")),
    R("wl.sav.low", "wealth", 3, lambda c:
      (c.sav(2) <= 25 or c.sav(11) <= 25) and
      yes(f"SAV: 2nd house {c.sav(2)}, 11th house {c.sav(11)}. At least one wealth house is "
          f"under-fuelled and will not hold what the other earns.", -1)),
    R("wl.vipreeta", "wealth", 3, lambda c:
      len([h for h in (6, 8, 12) if c.house_of_lord(h) in DUSTHANA]) >= 2 and
      yes("Vipreeta raja yoga: dusthana lords sit in dusthanas. Fortune reverses through crises "
          "that others do not survive. This is a real yoga and it is routinely missed by engines "
          "that only test for benefic placements.")),
]

# ==================================================================== HEALTH

HEALTH = [
    R("hl.1l.strong", "health", 3, lambda c:
      c.strong(c.lord_of(1)) and c.benefited(1) and
      yes("Lagna lord dignified with benefic support. Resilient constitution.")),
    R("hl.1l.weak", "health", 3, lambda c:
      c.weak(c.lord_of(1)) and
      yes(f"Lagna lord {PN[c.lord_of(1)]} is weak. The pattern is recurring dips in vitality rather "
          f"than any one named illness.", -1)),
    R("hl.6.chronic", "health", 3, lambda c:
      [p for p in c.occupants(6) if p in ("Sa", "Ra", "Ke")] and
      yes(f"{', '.join(PN[p] for p in c.occupants(6) if p in ('Sa','Ra','Ke'))} in the 6th. Chronic "
          f"rather than acute: slow onset, slow diagnosis, slow resolution.", -1)),
    R("hl.8.occupied", "health", 3, lambda c:
      c.occupants(8) and
      yes(f"{', '.join(PN[p] for p in c.occupants(8))} in the 8th. The body systems these planets "
          f"govern carry the long-term vulnerability.", -1)),
    R("hl.sav1", "health", 2, lambda c:
      c.sav(1) <= 25 and yes(f"Lagna SAV {c.sav(1)}. Low baseline reserve.", -1)),
    R("hl.moon.afflicted", "health", 2, lambda c:
      (c.conjunct("Mo", "Sa") or c.conjunct("Mo", "Ke")) and
      yes("Moon afflicted by Saturn or Ketu. Sleep, mood and appetite are the early warning system "
          "in this chart; treat changes there as data, not as personality.", -1)),
    R("hl.jup.lagna", "health", 2, lambda c:
      c.aspects_house("Ju", 1) and yes("Jupiter aspects the Lagna. The classical protective aspect.")),
]


DOMAINS = {
    "career": CAREER,
    "job_vs_business": JOB_BUSINESS,
    "marriage": MARRIAGE,
    "divorce": DIVORCE,
    "love": LOVE,
    "wealth": WEALTH,
    "health": HEALTH,
}

# --------------------------------------------------- timing significator sets

TIMING_SETS = {
    "marriage": lambda c: {c.lord_of(2), c.lord_of(7), c.lord_of(11), "Ve"} |
                          set(c.occupants(7)) | {c.karaka("Darakaraka")},
    "career": lambda c: {c.lord_of(6), c.lord_of(10), c.lord_of(11), c.karaka("Amatyakaraka")} |
                        set(c.occupants(10)),
    "wealth": lambda c: {c.lord_of(2), c.lord_of(11), c.lord_of(5), c.lord_of(9)},
    "breakup": lambda c: {c.lord_of(6), c.lord_of(8), c.lord_of(12)} & set(c.P) |
                         {c.lord_of(5)},
    "health": lambda c: {c.lord_of(6), c.lord_of(8), c.lord_of(12)},
}


def spouse_portrait(c: Ctx) -> dict:
    """Descriptive rather than scored. Six independent testimonies, reconciled."""
    sign7 = c.sign_of_house(7)
    l7 = c.lord_of(7)
    dk = c.karaka("Darakaraka")
    element = ["Fire", "Earth", "Air", "Water"][sign7 % 4]
    build = {"Fire": "lean, quick-moving, high colour",
             "Earth": "solid, well-proportioned, unhurried",
             "Air": "tall or long-limbed, restless hands",
             "Water": "soft-featured, full face, changeable weight"}[element]
    temper = {
        "Ma": "direct to the point of blunt, competitive, quick to anger and quick to forget",
        "Ve": "charming, appearance-conscious, conflict-avoidant",
        "Me": "talkative, analytical, restless, younger-seeming than their age",
        "Ju": "principled, advisory, inclined to lecture, generous",
        "Sa": "reserved, dutiful, slow to warm, dependable once committed",
        "Su": "proud, needs to be seen as the authority, dignified",
        "Mo": "emotionally attuned, moody, home-centred",
        "Ra": "unconventional, ambitious, hard to read",
        "Ke": "detached, spiritually inclined, emotionally elsewhere",
    }
    trade = {
        "Su": "government, medicine, administration",
        "Mo": "public-facing work, hospitality, care, liquids, or the family business",
        "Ma": "engineering, defence, surgery, real estate, sport",
        "Me": "accounts, writing, software, teaching, trade, brokerage",
        "Ju": "law, finance, education, advisory, clergy",
        "Ve": "design, media, fashion, luxury goods, arts, HR",
        "Sa": "industry, mining, logistics, civil service, long-tenure institutional work",
        "Ra": "technology, foreign firms, import-export, newly invented fields",
        "Ke": "research, pharmaceuticals, investigative or spiritual work",
    }
    from ..core.ephemeris import SIGN_LORD
    d9_l7 = SIGN_LORD[c.P[l7].vargas["D9"]]
    d10_10 = SIGN_LORD[(c.P["Su"].vargas["D10"] + 9) % 12]

    return {
        "appearance": f"The 7th falls in {SG[sign7]}, so expect {build}."
                      + (f" {', '.join(PN[p] for p in c.occupants(7))} in the 7th modifies this."
                         if c.occupants(7) else ""),
        "behaviour": f"7th lord {PN[l7]} and Darakaraka {PN[dk]}: {temper[l7]}"
                     + (f", overlaid with a {PN[dk]} streak — {temper[dk]}." if dk != l7 else "."),
        "profession": f"From the 7th lord: {trade[l7]}. Navamsha cross-check via {PN[d9_l7]} adds "
                      f"{trade[d9_l7]}. The D10 10th lord {PN[d10_10]} points to {trade[d10_10]}. "
                      f"Where two of the three agree, say it plainly; where they do not, offer both.",
        "in_laws": (f"Father-in-law is the 9th from the 7th, that is your 3rd. "
                    f"{'Afflicted — friction from that side.' if c.afflicted(3) else 'Clean — workable.'} "
                    f"Mother-in-law is the 4th from the 7th, your 10th. "
                    f"{'Malefic pressure — assertive or interfering.' if c.afflicted(10) else 'Unafflicted — settles.'}"),
        "wealth_after": (f"The 8th holds joint finance and the spouse's resources, at {c.sav(8)} SAV "
                         f"bindus. "
                         + ("Material position improves after marriage."
                            if c.sav(8) >= 30 or c.strong(c.lord_of(8))
                            else "Wealth after marriage comes from your own 2nd and 11th rather "
                                 "than the partner's side.")),
        "relocation": ("7th lord or Rahu touches the 4th/12th axis. Relocation around marriage is "
                       "likely, possibly far."
                       if c.house_of_lord(7) in (4, 12) or c.house_of("Ra") == 4
                       else "No strong relocation signature. Residence pattern stays close to the "
                            "existing one."),
        "physical": ("The 12th, which governs bed comforts, carries affliction. Physical "
                     "compatibility needs deliberate attention rather than assumption."
                     if c.afflicted(12) else
                     "The 12th is unafflicted. Physical compatibility is not a structural problem."),
        "mental": ("The Moon has benefic support. Emotional attunement comes easily."
                   if c.aspects_planet("Ju", "Mo") or c.conjunct("Mo", "Ve") else
                   "The Moon lacks direct benefic support. Mental compatibility depends heavily on "
                   "the partner's own Moon; run a synastry check before concluding."),
    }
