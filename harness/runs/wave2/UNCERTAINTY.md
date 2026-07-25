# Sabot — statistical uncertainty for the wave-2 results (SPEC v0.2.1)

Regenerate with `python scripts/score_uncertainty.py`; `--check` fails on
drift. Deterministic, no LLM, no network, Python 3.9+ standard library only.
Reads only `wave2-rows.json`, the 150 clean baseline traces under
`runs/wave2/`, and the frozen wave-1 matrix under `runs/matrix/`.

**Nothing here moves a published number.** Every point column below is
recomputed from the raw data and reproduces what is already published; the new
material is the interval columns. This file closes the one substantive gap an
external reviewer named in the wave-2 package: every published figure was a
point estimate over 5 seeds with correlated cells, carrying no confidence
intervals and no paired effect estimates.

## Method

**Unit of observation vs unit of resampling.** The scoreboard's unit is a CELL
(framework x config x task x operator x seed). Cells are not independent: the
five repetitions of a cell share a task, a fault payload and a pipeline model,
and an entire SEED shares one draw of run-to-run sampling noise across every
cell it contributes. A binomial interval over the 786 valid wave-2 cells would
treat 786 correlated observations as 786 independent ones, and would be far too
narrow.

**So the bootstrap resamples SEEDS, not cells** — a cluster bootstrap on the
one axis this design actually replicates. Each resample draws 5 seeds with
replacement and recomputes every rate from the cells those seeds contributed.
Wave 1 and wave 2 reuse the same registered seeds verbatim (11, 12, 13, 14, 15;
seeds/wave2.json), so one drawn seed multiset evaluates both waves and the
headline contrast stays seed-paired.

**The intervals are exact, not simulated.** A size-5 resample with replacement
of 5 clusters has only C(9, 4) = 126 distinct multisets (5**5 = 3125 ordered
draws). This script enumerates all 126 with their exact multinomial weights, so
the percentile CIs below carry **zero Monte-Carlo error**. Cross-check: an
ordinary Monte-Carlo cluster bootstrap (20,000 draws, fixed documented seed)
puts the headline median CI at [52.3, 58.0] against the exact [52.3, 58.0].

**Discreteness is the price, and it is stated per number.** With at most 126
support points a 2.5/97.5 percentile is read off a coarse lattice. Percentiles
use the type-1 (inverse-CDF) definition — the smallest value whose cumulative
weight reaches the tail probability — so every endpoint is a value the
bootstrap actually produced; interpolating would invent resolution this design
does not have. The `support` column publishes how many DISTINCT values each
statistic's bootstrap distribution has, so a reader can see exactly how coarse
each interval is. Two companions travel with the CI for the same reason:

* **Seed-jackknife range** — the exact min and max over the 5
  leave-one-seed-out datasets. Not a rival interval: it answers "how far does
  dropping any one seed move this number?", which a percentile cannot.
* **Bootstrap range** — the min and max attainable over all 126 resamples, i.e.
  what the number becomes in the degenerate case where all 5 draws land on a
  single seed.

**A sign test on 5 seeds cannot reach p < 0.05.** The most extreme possible
outcome (5/5 seeds agreeing) has a two-sided exact p of 2/2**5 = 0.0625. The
per-seed columns below are therefore **descriptions of direction, never
significance claims**, and this file states that arithmetic rather than letting
a reader assume otherwise.

**What seed resampling cannot capture.** It captures seed-to-seed sampling
variation at fixed everything-else. It does **not** capture pipeline-model
version drift, framework version drift, task-suite selection (5 tasks), or
operator-suite selection (6 operators). Those are fixed constants of this
design, not sampled populations, and no resampling of 5 seeds can put an
interval on them. The README's standing caveat still governs: these are results
about these frameworks with this model at these versions, not laws of nature.

## 1. The headline contrast: 16.7% -> 55.0%

Both medians are the pre-registered aggregator (SPEC section 7): the median
across the three FRAMEWORKS with configs pooled.

| quantity | point | 95% cluster-bootstrap CI | seed-jackknife range | bootstrap range | support |
|---|---|---|---|---|---|
| wave-1 median hard-tier (frozen matrix, 828 valid cells) | **16.7%** | [15.6, 17.8] | 16.2 to 17.1 | 15.0 to 18.5 | 36 |
| wave-2 median union (published headline, 786 valid cells) | **55.0%** | [52.3, 58.0] | 53.8 to 56.1 | 50.0 to 60.0 | 51 |
| seed-paired difference of medians | **+38.3 pp** | [+36.4, +40.6] | +37.6 to +39.5 | +35.0 to +41.5 | 100 |
| strictly per-cell paired effect (726 paired cells) | **+39.4 pp** | [+37.0, +41.4] | +38.7 to +40.4 | +35.4 to +41.8 | 126 |

The two effect rows answer different questions and both are reported. The
**difference of medians** puts an interval on the contrast exactly as published
(wave-1's median over its own 828 valid cells, wave-2's over its 786),
seed-paired because the same drawn seed multiset feeds both. The **strictly
per-cell paired** effect is the reviewer's estimand: the mean of `wave2_union -
wave1_hard` over the 726 cells that have a scored wave-1 partner, so each cell
is its own control (same framework, config, task, operator and seed; wave-1
rules vs wave-2 rules). It runs on a slightly smaller population — 60 of the
786 valid wave-2 cells have no wave-1 partner, from the wave-2 O4 landing-probe
exclusions and the wave-1 BASELINE_FAIL exclusions — which is why its point
value differs slightly from the difference of medians. Neither replaces a
published number.

**Both intervals exclude zero by a wide margin.** With five seeds that is about
as strong as this design can state it; see the limitations for what the
interval does and does not cover.

## 2. Wave-2 detection by framework x config, with the strict floor

The README's convention is that the strict injection-evidence floor and the
published union are quoted as a **pair**, with the truth in between. Both now
carry intervals, computed on the same resamples.

| row | valid | published union | 95% CI | jackknife range | support | strict floor | 95% CI |
|---|---|---|---|---|---|---|---|
| langgraph/default | 138 | **55.1%** (76/138) | [51.6, 58.0] | 53.7 to 56.1 | 21 | 47.8% (66/138) | [43.7, 51.3] |
| langgraph/guardrail | 144 | **54.9%** (79/144) | [51.4, 58.0] | 53.5 to 56.1 | 41 | 48.6% (70/144) | [43.2, 52.7] |
| crewai/default | 150 | **53.3%** (80/150) | [49.3, 57.3] | 51.7 to 55.0 | 21 | 51.3% (77/150) | [48.7, 54.7] |
| crewai/guardrail | 138 | **53.6%** (74/138) | [51.4, 56.1] | 52.6 to 54.6 | 35 | 52.2% (72/138) | [48.6, 55.6] |
| autogen/default | 144 | **55.6%** (80/144) | [52.2, 59.7] | 53.5 to 56.7 | 46 | 52.8% (76/144) | [49.2, 56.7] |
| autogen/guardrail | 72 | **84.7%** (61/72) | [77.8, 91.3] | 82.5 to 87.7 | 48 | 55.6% (40/72) | [50.7, 59.7] |

### The scoreboard cannot rank the five standard rows

Every pairwise seed-paired difference between the five standard rows has a 95%
CI containing zero. The 53.3-55.6% spread across those rows is **not** evidence
that any framework or config detects better than another; it is inside seed
noise. That is a limitation of five seeds, not a finding about the frameworks.

| comparison | difference | 95% CI | contains 0 |
|---|---|---|---|
| langgraph/default - langgraph/guardrail | +0.2 pp | [+0.0, +0.5] | yes |
| langgraph/default - crewai/default | +1.7 pp | [-4.7, +6.7] | yes |
| langgraph/default - crewai/guardrail | +1.4 pp | [-1.3, +4.0] | yes |
| langgraph/default - autogen/default | -0.5 pp | [-3.8, +2.8] | yes |
| langgraph/guardrail - crewai/default | +1.5 pp | [-4.7, +6.7] | yes |
| langgraph/guardrail - crewai/guardrail | +1.2 pp | [-1.4, +3.9] | yes |
| langgraph/guardrail - autogen/default | -0.7 pp | [-4.0, +2.6] | yes |
| crewai/default - crewai/guardrail | -0.3 pp | [-5.3, +5.9] | yes |
| crewai/default - autogen/default | -2.2 pp | [-9.3, +5.2] | yes |
| crewai/guardrail - autogen/default | -1.9 pp | [-6.2, +2.1] | yes |

All 10 comparisons contain zero.

One entry deserves its own note, because its interval is degenerate rather than
informative: `langgraph/default` and `langgraph/guardrail` have the **identical
per-seed union rate on all five seeds** (56.7, 50.0, 60.0, 56.7, 50.0). Their
+0.2 pp pooled difference is therefore purely a denominator artifact — 138 vs
144 valid cells, from wave-2 exclusions — and no resample can push it below
zero, which is why its lower endpoint is exactly 0.0 rather than negative.

### Pooled by framework — the three inputs to the median

| framework | valid | pooled union | 95% CI | jackknife range | support |
|---|---|---|---|---|---|
| autogen | 216 | **65.3%** (141/216) | [63.3, 66.7] | 64.9 to 66.1 | 47 |
| crewai | 288 | **53.5%** (154/288) | [51.4, 55.2] | 53.0 to 54.4 | 55 |
| langgraph | 282 | **55.0%** (155/282) | [51.5, 58.0] | 53.6 to 56.1 | 47 |

## 3. Paired per-framework effects (the reviewer's specific ask)

Per row, the mean per-cell paired difference `wave2_union - wave1_hard` over
the cells that have a scored wave-1 partner. The `wave-1 hard` column here is
the same paired column the README publishes.

| row | paired cells | wave-1 hard | wave-2 union | paired effect | 95% CI | jackknife range | per-seed effects (pp) | seeds positive | exact sign p |
|---|---|---|---|---|---|---|---|---|---|
| langgraph/default | 138 | 17.4% (24/138) | 55.1% (76/138) | **+37.7 pp** | [+35.6, +39.6] | +37.0 to +38.6 | +40.0, +37.5, +36.7, +40.0, +33.3 | 5/5 | 0.0625 |
| langgraph/guardrail | 126 | 15.1% (19/126) | 52.4% (66/126) | **+37.3 pp** | [+31.0, +42.5] | +35.3 to +40.2 | +37.5, +37.5, +45.8, +40.0, +25.0 | 5/5 | 0.0625 |
| crewai/default | 132 | 18.2% (24/132) | 52.3% (69/132) | **+34.1 pp** | [+27.8, +41.7] | +30.4 to +36.1 | +37.5, +29.2, +25.0, +30.0, +46.7 | 5/5 | 0.0625 |
| crewai/guardrail | 126 | 21.4% (27/126) | 54.0% (68/126) | **+32.5 pp** | [+27.5, +36.7] | +31.4 to +35.4 | +33.3, +23.3, +37.5, +37.5, +33.3 | 5/5 | 0.0625 |
| autogen/default | 132 | 20.5% (27/132) | 55.3% (73/132) | **+34.8 pp** | [+29.7, +41.3] | +32.4 to +36.3 | +30.0, +30.0, +45.8, +41.7, +29.2 | 5/5 | 0.0625 |
| autogen/guardrail | 72 | 8.3% (6/72) | 84.7% (61/72) | **+76.4 pp** | [+69.3, +84.1] | +73.7 to +78.9 | +86.7, +83.3, +66.7, +80.0, +66.7 | 5/5 | 0.0625 |

**Every row: all 5/5 seeds positive, every 95% CI strictly above zero.** Read
that as direction and consistency, not as p < 0.05 — the exact sign-test p of
0.0625 is the FLOOR of what 5 seeds can produce, and it is reported at that
floor on every row precisely because the test is saturated, not because the
effect is marginal. The CI, which uses the magnitudes rather than only the
signs, is the informative statement here.

**The Magentic row's paired effect must be read against its carve-out.** Its 72
paired cells are the pre-registered carve-out subset only (O1/O4/O5; SPEC
10.6), so its effect is not comparable cell-for-cell with the standard rows,
which pair across all six operators. Magentic (autogen/guardrail) rows carry
the wave-2 QC caveats wherever they appear: the row's 84.7% union is the
permissive pre-registered mapping reading, whose Magentic acts are 100%
stall-ledger noise, so **73.6% flags-only is the honest number for the row**
(QC finding 1); the row is scored over the pre-registered Magentic carve-out
subset (O1/O4/O5 only, 72 cells, SPEC 10.6), not the full operator suite; its
wave-1 comparator is ~0% true detection either way (wave-1 footnote 5); and the
FLAGS contract itself induces Magentic stalls (QC finding 2). An interval
around a number does not launder any of that — it is an interval around a
caveated number.

### The Magentic row on its honest (flags-only) surface

| quantity | point | 95% CI | jackknife range | support |
|---|---|---|---|---|
| Magentic flags-only detection (the quoted number) | **73.6%** (53/72) | [69.3, 78.8] | 71.7 to 75.4 | 21 |
| Magentic paired effect, flags-only vs wave-1 hard | **+65.3 pp** | [+61.3, +69.7] | +63.3 to +66.7 | 19 |

Per-seed effects on that surface: +66.7, +75.0, +60.0, +66.7, +60.0; 5/5
positive. The flags-only surface is the one to quote: it is the honest reading
of the row and it drops the 8 union-only cells that fire on stall noise alone.

## 4. Intervals for the other published wave-2 numbers

| published number | as published | point | 95% CI | jackknife range | support |
|---|---|---|---|---|---|
| recovery-without-detection, union surface | 26.1% | 26.1% | [24.8, 27.8] | 25.3 to 26.6 | 91 |
| recovery-without-detection, frozen wave-1 surface | 50.0% | 50.0% | [49.1, 51.1] | 49.5 to 50.4 | 114 |
| Magentic flags-only detection | 73.6% | 73.6% | [69.3, 78.8] | 71.7 to 75.4 | 21 |
| O4 honest reading (mapping-only, Magentic stall acts zeroed) | 9.8% | 9.8% | [4.3, 14.0] | 8.7 to 12.1 | 56 |
| O4 anchored-flags rate on fault runs | 24.5% | 24.5% | [20.3, 28.7] | 22.8 to 25.9 | 76 |
| O4 clean-baseline false-anchor base rate | 26.0% | 26.0% | [23.3, 28.7] | 25.0 to 26.7 | 6 |

**The O4 null is now an interval statement, not just a point comparison.** The
fault-run anchored rate [20.3, 28.7] and the clean-baseline false-anchor base
rate [23.3, 28.7] overlap almost completely. The published conclusion — the O4
flag surface carries no signal, and the honest O4 number is the mapping-only
9.8% — survives the addition of uncertainty, and is if anything stated more
firmly by it.

### Clean-baseline false-anchor base rates, with intervals

The published base-rate table (QC finding 3), recomputed over the same 150
clean baseline runs with a seed-cluster CI on each rate. These are the
comparators every anchored-text detection number must be read against.

| operator | published | point | 95% CI | jackknife range | support |
|---|---|---|---|---|---|
| O1 | 32.7% | 32.7% (49/150) | [30.0, 36.7] | 30.8 to 33.3 | 15 |
| O2 | 5.3% | 5.3% (8/150) | [1.3, 9.3] | 4.2 to 6.7 | 15 |
| O3 | 12.7% | 12.7% (19/150) | [10.7, 14.7] | 11.7 to 13.3 | 11 |
| O4 | 26.0% | 26.0% (39/150) | [23.3, 28.7] | 25.0 to 26.7 | 6 |
| O5 | 24.0% | 24.0% (36/150) | [18.0, 30.0] | 21.7 to 26.7 | 30 |
| O6 | 1.3% | 1.3% (2/150) | [0.0, 2.7] | 0.8 to 1.7 | 6 |

## 5. Is the headline robust to the Magentic caveat?

Yes, and the demonstration is exact. Rescoring the Magentic row on its honest
flags-only surface (73.6% instead of 84.7%) and leaving the five standard rows
untouched leaves the cross-framework median at 54.9645% with the same CI [52.3,
58.0] — unchanged in every digit. AutoGen's pooled rate sits above the median
under both readings, so the Magentic row never selects the median; it only sits
above it. The published 55.0% headline therefore does not depend on the reading
of the row that carries the most caveats.

## 6. The widest intervals in this file, stated up front

Wide intervals are the finding, not an embarrassment to bury. This table is
derived from every interval this file publishes, not hand-picked: the 8 widest
of the 48 intervals above.

| quantity | point | 95% CI | width |
|---|---|---|---|
| autogen/guardrail paired effect | +76.4 pp | [+69.3, +84.1] | 14.7 pp |
| crewai/default - autogen/default (union) | -2.2 pp | [-9.3, +5.2] | 14.5 pp |
| crewai/default paired effect | +34.1 pp | [+27.8, +41.7] | 13.9 pp |
| autogen/guardrail union | 84.7% | [77.8, 91.3] | 13.5 pp |
| O5 clean-baseline false-anchor base rate | 24.0% | [18.0, 30.0] | 12.0 pp |
| autogen/default paired effect | +34.8 pp | [+29.7, +41.3] | 11.6 pp |
| langgraph/guardrail paired effect | +37.3 pp | [+31.0, +42.5] | 11.5 pp |
| langgraph/guardrail - crewai/default (union) | +1.5 pp | [-4.7, +6.7] | 11.3 pp |

The pattern is the honest one and it is worth saying plainly. The widest
intervals in this file are (a) the framework-vs-framework comparisons, which is
exactly why section 2 says the scoreboard cannot be read as a ranking, and (b)
anything computed on the 72-cell Magentic carve-out, the smallest row in the
study. A ~15-point-wide interval on the Magentic paired effect means the
*direction* of that row's lift is solid and its *magnitude* is not pinned down
better than "very large". Anyone quoting a Magentic lift to one decimal place
is over-reading it.

## Limitations

1. **Five clusters is few, and the intervals are correspondingly coarse.**
   Every CI here is read off a distribution with at most 126 support points,
   and several have far fewer — the `support` columns publish the exact number
   per statistic. A 2.5% tail on 126 points is about three points of weight.
   The seed-jackknife range is published beside every interval for exactly this
   reason.
2. **A sign test on 5 seeds cannot reach p < 0.05.** The two-sided exact
   minimum is 0.0625. Every per-seed consistency statement in this file is
   descriptive.
3. **Seed-level resampling captures seed-to-seed sampling variation only.** It
   cannot capture pipeline-model version drift, framework version drift,
   task-suite selection (5 tasks), or operator-suite selection (6 operators).
   Those are fixed constants of this design, not sampled populations. If the
   pipeline model is silently updated, none of these intervals covers that; the
   published version pins and the raw trace corpus are the defence there, not
   statistics.
4. **The five standard scoreboard rows are statistically indistinguishable from
   each other** (section 2). Sabot's cross-framework spread is not yet a
   ranking, and this file is the reason to stop reading it as one.
5. **No multiplicity correction is applied.** This file reports 48 intervals;
   at 95% nominal coverage some would be expected to miss even under the null.
   The pre-registered headline is a single comparison (SPEC section 7) and is
   the confirmatory one; everything else here is descriptive.
6. **The paired grid is 726 of 786 valid wave-2 cells.** 60 cells have no
   scored wave-1 partner (wave-2 O4 landing-probe exclusions and wave-1
   BASELINE_FAIL exclusions), so the paired estimates run on a slightly smaller
   population than the published row rates. Both populations are stated in
   every table.
7. **The Magentic row's intervals do not launder its caveats.** Magentic
   (autogen/guardrail) rows carry the wave-2 QC caveats wherever they appear:
   the row's 84.7% union is the permissive pre-registered mapping reading,
   whose Magentic acts are 100% stall-ledger noise, so **73.6% flags-only is
   the honest number for the row** (QC finding 1); the row is scored over the
   pre-registered Magentic carve-out subset (O1/O4/O5 only, 72 cells, SPEC
   10.6), not the full operator suite; its wave-1 comparator is ~0% true
   detection either way (wave-1 footnote 5); and the FLAGS contract itself
   induces Magentic stalls (QC finding 2). An interval around a number does not
   launder any of that — it is an interval around a caveated number.
8. **A cluster bootstrap on 5 clusters is known to under-cover.** The
   percentile interval is not calibrated to be exactly 95% at this cluster
   count, and no small-sample correction (BCa, t-adjustment) is applied — with
   5 clusters the bias and acceleration terms would themselves be estimated
   from 5 points and would add false precision. Treat every interval here as an
   indicative width, not as a calibrated 95% guarantee.
