# Jyotish workbench — architecture

```
Browser ──► Vercel (Next.js)                    Render (FastAPI + Docker)
            ├─ /                 dashboard      ├─ /chart          full chart JSON
            ├─ /api/jyotish/*    proxy ────────►├─ /predict/{domain}
            │  adds X-API-Key                   ├─ /predict/all
            │  hides the origin                 ├─ /varshphal
            └─ static assets on the CDN         ├─ /transits
                                                └─ /read-chart-image
                                                     └─► Claude Vision / Tesseract
```

Two rules drive the split. Swiss Ephemeris is a C library with a 6 MB data file
and no usable JavaScript equivalent, so it lives on the server. Everything the
user touches is latency-sensitive, so it lives on the CDN.

---

## Why the proxy route exists

Calling Render directly from the browser would work and is the wrong choice.

| Direct fetch | Through `/api/jyotish/*` |
|---|---|
| API key must be `NEXT_PUBLIC_`, so it ships to every visitor | key stays in Vercel's server env |
| CORS preflight on every request | same-origin, no preflight |
| Render URL is public, so anyone can hammer it | origin is hidden; add rate limiting at the proxy |
| Cold-start timeout surfaces as a raw network error | proxy converts it into a 504 with a sentence a person can read |

The route handler is a catch-all, so adding a backend endpoint needs no
frontend change.

---

## Data flow for one reading

1. User submits birth data. `tz_offset` is the offset **at the moment of birth**,
   not today's. India has been +5:30 since 1955, but a 1941 Bombay birth is
   +6:30, and every Indian chart cast before 1942 with +5:30 is wrong by an
   hour. Store the offset, never the timezone name alone.
2. `build_chart` computes sidereal longitudes, Placidus cusps, dignities,
   nakshatras, sub-lords and nine divisional signs in one pass. `lru_cache` on
   the six inputs means repeat requests for the same chart cost nothing.
3. `ashtakavarga`, `jaimini_block` and `significators` derive from that chart.
4. A `Ctx` object wraps all four. It is the only interface rules are allowed to
   touch, so a rule can never reach into raw longitudes and invent its own
   house system.
5. Rules run. Each returns a sentence or nothing.
6. The aggregator turns fired rules into a score, a confidence, and a verdict.

---

## The logic-tree question, answered honestly

You asked for the exact `if/else` logic. I'd push back on the framing, and here
is why with a concrete case.

Take marriage timing on a chart with all of these:

- 7th lord exalted (strongly positive)
- Saturn in the 7th (delay)
- Upapada in the 12th (Jaimini strain)
- 7th cuspal sub-lord signifies 2, 7, 11 (KP promise)
- 7th house SAV 22 (weak)

A decision tree has to pick an order. Check the KP promise first and you output
"marriage is supported". Check Upapada first and you output "strained marriage
line". Same chart, opposite readings, and the difference is an accident of how
the author happened to nest the branches. That is not a modelling limitation
you can code around; it is what trees do.

So the engine scores instead:

```python
Rule(id="mar.7l.dusthana", weight=4, school="parashari",
     test=lambda c: c.house_of_lord(7) in DUSTHANA and
                    yes("7th lord in house ...", polarity=-1))
```

A fired rule contributes `weight × polarity`. The domain verdict is

```
score      = (positive_weight − negative_weight) / total_weight × 100
confidence = min(100, total_weight × 6)
```

Score says which way the evidence points. Confidence says how much evidence
there was. **+80 from two rules is a weaker claim than +40 from eleven**, and
collapsing those into one number is the mistake most astrology software makes.

Weights, 1 to 5:

| w | meaning | example |
|---|---|---|
| 5 | classical yoga with explicit textual basis, few exceptions | Dharma-karmadhipati; malefics in the 2nd from Upapada |
| 4 | strong single factor | 7th lord in a dusthana; KP cuspal sub-lord promise |
| 3 | ordinary supporting factor | SAV above 32; Amatyakaraka in a kendra |
| 2 | modifier | Saturn aspecting the 10th |
| 1 | colour, not evidence | elemental temperament |

### Cross-school corroboration

`cross_check()` tags every hit with the school it came from and reports which
schools actually agree with the final direction. A verdict resting only on KP
gets `corroborated: false`. The UI should say so rather than presenting a single
KP rule as settled. This one field does more for output quality than another
fifty rules would.

### Two-sided questions

Job vs business and love vs arranged are not positive/negative axes, so they use
`two_sided()`: two tagged rule sets scored independently and compared. Below a
lean of 3 the answer is "balanced", which for job vs business is a real finding
and usually means a salaried first half and an independent second.

### Neecha bhanga

`Ctx.neecha_bhanga()` exists because cancelled debilitation is the commonest
false negative in automated reading. An engine that sees "Venus debilitated" and
stops will call a good marriage chart bad. Any rule testing weakness on a
debilitated planet must call this first.

---

## Timing

Two independent methods, deliberately not merged:

**Vimshottari.** `windows_for(tree, significators, depth)` returns periods where
every level of the dasha path is a significator. Depth 2 gives you a year, depth
3 gives you a month. `TIMING_SETS` defines the significator set per domain:
marriage is `{2nd lord, 7th lord, 11th lord, Venus, occupants of the 7th,
Darakaraka}`.

**Transit confirmation.** Never generate a date from transits; use them to
confirm a dasha window. For marriage: Jupiter over the 7th from Lagna or Moon,
or over the natal 7th lord. For career: Saturn over the 10th, Jupiter over the
11th. `/transits` also returns the KP ruling planets of the moment, which is
what you use to confirm a specific date once the window is fixed.

A prediction quoting a window backed by both is worth stating. One backed by
only the dasha should be phrased as a window, not a date.

---

## The OCR path

The North Indian chart is a fixed diagram. Twelve regions that never move,
house 1 always the top centre diamond, numbering anticlockwise. So layout
inference is not the problem — glyph recognition under bad lighting, mixed
Devanagari and Latin abbreviations, and handwriting is.

1. **Rectify.** Canny plus contour approximation finds the outer square, then a
   perspective warp to a 400×400 canvas. Skew, phone-camera angle and crop all
   disappear here. Everything downstream can assume canonical geometry.
2. **Read.** Claude Vision on the whole rectified image with a strict JSON
   schema. Whole-image beats per-crop because the model can use the constraint
   that rashi numbers run in an unbroken anticlockwise sequence to fix a single
   misread digit.
3. **Fall back.** Tesseract per cropped polygon when the vision call fails or
   returns confidence below 0.55. Deterministic, offline, cheap.
4. **Validate, and this is the part that matters.** Four structural invariants:
   - all twelve houses present
   - rashi numbers form a valid anticlockwise run — one digit disagreeing
     against eleven agreeing gets repaired automatically and the repair is
     reported
   - each graha appears exactly once
   - Rahu and Ketu are exactly six houses apart

   Any failure lowers confidence rather than returning a plausible chart. A
   confidently wrong chart is worse than no chart.

**The honest limitation:** an image gives signs and houses, nothing more. No
degrees means no nakshatra, no sub-lord, no Vimshottari, no Ashtakavarga, no
KP at all. `to_partial_chart()` marks the read `sign_and_house_only`, and rules
touching degrees must be filtered out before running against it. The reader is
for triage when someone has a printout and not a birth time. It does not replace
birth data.

---

## Deployment

### Backend on Render

1. Download `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` from
   `astro.com/ftp/swisseph/ephe/` into `backend/ephe/`. About 6 MB, covers
   1800–2400. Without them pyswisseph silently falls back to Moshier — good
   enough for rashi, occasionally enough to move a cuspal sub-lord. `/health`
   reports which mode is live.
2. Push `backend/` to GitHub. In Render: New → Web Service → point at the repo,
   runtime Docker, and it picks up `render.yaml`.
3. Set `ANTHROPIC_API_KEY` by hand in the dashboard. `API_KEY` is generated for
   you — copy it.
4. Set `ALLOWED_ORIGINS` to your Vercel domain once you have it.

The Dockerfile installs `tesseract-ocr-hin` for Devanagari and `libgl1` for
OpenCV, both of which the slim base image lacks and both of which fail at
import time rather than at build time if you forget.

### Frontend on Vercel

```bash
cd frontend && vercel
vercel env add JYOTISH_API_URL production   # https://jyotish-api.onrender.com
vercel env add JYOTISH_API_KEY production   # the value Render generated
```

Neither is `NEXT_PUBLIC_`. Both are read only inside the route handler.

### Cold starts, the thing that will actually bite you

Render's free tier sleeps after 15 minutes idle and takes 30–50 seconds to wake.
That is longer than any user will wait staring at a spinner. Three mitigations,
in order of preference:

1. Call `warmBackend()` on page load. The container wakes while the user is
   still typing their birth details, and by submit time it is warm. This alone
   fixes the common case.
2. Ping `/health` every 10 minutes from a Vercel cron job. Keeps it awake during
   working hours. Free, slightly against the spirit of the free tier.
3. Pay for the $7 starter instance. If this is going in front of real users,
   do this.

The proxy's `maxDuration = 60` and 55-second `AbortSignal.timeout` exist so a
cold start surfaces as a readable 504 rather than a hung request.

---

## What I would build next, in order

1. **Birth-time rectification.** Everything KP asserts collapses if the time is
   off by four minutes. A rectification tool that fits past events against
   candidate Ascendant degrees is worth more than any new rule.
2. **Synastry.** Half the marriage questions here need both charts. Ashtakoot
   Guna Milan is the expected surface; Kuja dosha cancellation and 7th-lord
   cross-comparison do the real work.
3. **Rule provenance.** Add a `source` field citing the classical text per rule.
   When a rule produces a bad reading you need to know whether the rule is wrong
   or the implementation is.
4. **Shadbala.** The engine's `strong()` and `weak()` are crude proxies. Real
   six-fold strength would let weights scale by planetary strength instead of
   being fixed.

---

## A note on framing the output

The engine is deterministic and it is transparent, which is what makes it
useful. It is not an oracle. The interface reflects this by showing the rules
that fired and their weights next to every verdict, so a practitioner can
disagree with a specific rule rather than with a black box, and a user can see
that a "strongly supported" verdict rests on four rules rather than fourteen.

Keep that. The moment predictions appear without their evidence, the tool stops
being a workbench and becomes something a person might act on more confidently
than the reasoning behind it warrants.
