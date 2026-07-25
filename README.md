# Sabot

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21539796.svg)](https://doi.org/10.5281/zenodo.21539796)
[![License: CC BY 4.0](https://img.shields.io/badge/spec%20%26%20results-CC%20BY%204.0-blue.svg)](LICENSE)
[![Harness: Apache 2.0](https://img.shields.io/badge/harness-Apache%202.0-blue.svg)](LICENSE-CODE)
[![SPEC](https://img.shields.io/badge/SPEC-v0.2.1-informational.svg)](SPEC.md)

**Crash-test ratings for agent stacks.** Sabot plants controlled faults inside a running
agent pipeline and scores what fraction of them the pipeline's **own** checks catch.

> **The finding.** Across 900 faults planted in live LangGraph, CrewAI and
> AutoGen/Magentic-One runs, the median detection rate by the pipelines' own reviewer
> stages and guardrails was **16.7%**. The most common outcome in *every* configuration
> — 51–61% of faults — was a **correct final answer with nothing ever flagging the
> fault**. Adding one requirement to the reviewer prompt (report what you noticed,
> before you rule) took the median to **55.0%** on the same 825 paired cells. But
> corrective action did not follow reporting: on the original surface,
> recovery-without-detection stayed at 50%. The checks were decorative; the fix makes
> the noticing *legible*, not acted on.
>
> Spec and anchors were registered publicly **before any scored run**. Negative
> results publish at equal prominence. [Wave-1 results](#wave-1-results-2026-07-23) ·
> [Wave-2 results](#wave-2-results-2026-07-24-the-fix-measured) · [Papers](papers/) ·
> [Limitations](#wave-2-results-2026-07-24-the-fix-measured)

One pipeline model, five replicate runs per cell, pinned framework versions — these are results
about these frameworks with this model at these versions, not laws of nature.

Every serious agent framework ships self-verification: reviewer agents, critic stages,
guardrail callbacks, voting. The industry's reliability story rests on those checks
working. Sabot is a standard (a frozen metric spec), a harness (a runnable tool), and a
public scoreboard measuring whether they do.

## The metric in one paragraph

Each planted fault gets three ordered verdicts — **DETECTED** (a component of the
pipeline itself flagged it), **REACTED** (the pipeline acted on the flag), **RECOVERED**
(the task still ended correct). The headline **Sabot Score** is the hard-tier detection
rate: only detection *acts* recorded by the framework's own surfaces count, adjudicated
deterministically against the published per-framework mapping in [SPEC.md](SPEC.md). A
cross-lineage LLM judge separately scores "noticed but not acted on" (the soft tier);
the gap between them — faults an agent saw and the system overrode — is published as its
own number. Full definitions, operators, mappings, and pre-registered interpretation
bands: [SPEC.md](SPEC.md).

## Try it: recompute the headline yourself, offline

No API key, no model calls, no virtualenv — the hard tier is deterministic by design, and
the raw traces for all 2,025 runs ship in this repo. That is what publishing traces is
*for*.

**Two version floors, and they are not in conflict.** The offline recompute and scoring
scripts under `harness/scripts/` are **Python 3.9+, standard library only** — no install
step, no third-party dependency, nothing to build. Running the *harness itself* — planting
faults in live agent pipelines — requires **Python 3.11+** plus the pinned framework
virtualenvs (`harness/pyproject.toml`, `harness/scripts/setup_venvs.sh`). Everything in
this section is the first kind:

```bash
git clone --depth 1 https://github.com/Jott2121/sabot && cd sabot/harness

# 1. the strict injection-evidence floor, verified against its frozen baseline
python3 scripts/score_strict.py --check
#    -> strict floor stable across 6 rows

# 2. the replicate-cluster bootstrap intervals, verified against their frozen baseline
python3 scripts/score_uncertainty.py --check
#    -> uncertainty stable across 24 pinned intervals; UNCERTAINTY.md byte-identical

# 3. rebuild the ENTIRE wave-2 scoreboard from the raw traces
python3 scripts/score_wave2.py --seeds-file ../seeds/wave2.json
git diff --stat runs/wave2/WAVE2-RESULTS.md
#    -> all 189 scored rows come back byte-identical. The only diff is the
#       hand-appended QC footnote block, which a re-score strips (footnote 9).
```

If a number in this repo disagrees with what those commands print, the repo is wrong and
we want the issue.

### One cell, end to end

The metric is easiest to see in a single published cell —
`langgraph/default/T1/O1/seed11`. The fault: a tool returned the source's surface-figure
`47.1` rewritten to `74.1`. The reviewer's mandated FLAGS line, recorded verbatim in
[`wave2-rows.json`](harness/runs/wave2/wave2-rows.json):

> source section 3.2 says "initially transcribed … at **74.1** µm RMS" but also refers to
> a superseded "47.1 µm" body figure; extracted governing value "41.7 µm RMS" is supported
> by Figure 2 and findings.

It quotes `74.1`, a string that exists only because the fault landed, so it scores as a
hard-tier detection. The cell's full verdict:

| `wave1_mapping` | `flags_anchored` | `union` | `reacted` | `recovered` |
|---|---|---|---|---|
| `false` | `true` | **`true`** | **`false`** | `true` |

Read the row left to right and you have the whole result. Under wave-1 rules this fault was
a **miss** — nothing in the pipeline emitted an act. Under the anomaly-first protocol it is
a **detection**, because the reviewer was finally asked to say what it saw. And `reacted` is
still **`false`**: it reported the contradiction, then approved anyway, and the task passed.
That is the finding, in one cell. The protocol bought visibility, not correction.

## Status

- `seeds/` — pre-registered per-wave seeds (SPEC §8): committed before any scored run,
  published with results.
- **2026-07-22:** SPEC v0.1 published. First scoreboard (LangGraph, CrewAI,
  AutoGen/Magentic-One) in progress; harness and raw traces publish here with the
  results. Interpretation bands are pre-registered in SPEC §7 *before* any data exists,
  and results publish regardless of what they show.
- **2026-07-23:** Wave-1 results, harness, and raw traces published (below). SPEC
  amended to v0.1.3 (pre-reveal disclosure amendment; see the Amendment log).
- **2026-07-24:** Wave-2 results published (below), together with **both preprints**
  ([papers/](papers/)) and the wave-2 evidence package. SPEC v0.2.0 — the
  anomaly-first protocol, all 30 anchors, and five predictions — was tagged
  *before any wave-2 scored run*.

## Wave-1 results (2026-07-23)

**Median hard-tier Sabot Score across the three frameworks: 16.7%** — the pre-registered
"full push" band. The dominant outcome in *every* scoreboard row (51–61% of valid
faults) is **recovery-without-detection**: the task output is correct while nothing in
the pipeline ever flags the injected fault. Trace analysis shows the pipeline model
frequently notices the anomaly and routes around it without emitting any act.

| framework | config | Sabot Score (hard) | soft notice | recovery w/o detection |
|---|---|---|---|---|
| LangGraph | default | 18.0% | 20.0% | 58.0% |
| LangGraph | guardrail | 15.2% | 17.4% | 60.6% |
| CrewAI | default | 18.2% | 18.9% | 56.8% |
| CrewAI | guardrail | 21.4% | 22.2% | 53.2% |
| AutoGen | default | 21.0% | 24.6% | 54.3% |
| AutoGen (Magentic-One) | guardrail | 4.0%† | 15.3% | 51.3% |

† Upper bound, structurally confounded — 75 of this row's 150 cells cannot
structurally detect, and its 6 counted detections are stall noise reproduced by
clean runs; on the comparable operator subset the two AutoGen configs are
indistinguishable (8.7% vs 8.0%). Never quote this row without
[footnotes 4–5](harness/RESULTS.md).

Full scoreboard with exclusion appendix and all footnotes:
[harness/RESULTS.md](harness/RESULTS.md). Pre-publication adversarial QC ledger:
[harness/docs/qc-wave1-2026-07-23.md](harness/docs/qc-wave1-2026-07-23.md). The
complete harness (Apache-2.0, see [LICENSE-CODE](LICENSE-CODE)), spend ledger, and
the raw trace corpus for every run — including the quarantine directories from both
disclosed infrastructure incidents — live under [harness/](harness/).

## Wave-2 results (2026-07-24): the fix, measured

Wave 1's dominant outcome was the pipeline noticing a fault and routing around it
because nothing ever asked it to report. Wave 2 tests that reading with **one change
at the review seam** — report every noticed inconsistency, quoting the exact
conflicting values, *before* emitting a verdict or artifact (SPEC §10.2) — and
re-runs the entire wave-1 matrix: same frameworks, configs, tasks, operators and
seeds, so every comparison is same-cell paired. 825 fault runs plus 150 re-baselined
controls. Anchors, predictions, and adjudication rules were pre-registered in the
tagged spec before any scored run.

**Median hard-tier detection rose from 16.7% to 55.0%.**

| framework | config | wave-1 hard (paired) | wave-2 union | strict floor‡ |
|---|---|---|---|---|
| LangGraph | default | 17.4% | 55.1% | 47.8% |
| LangGraph | guardrail | 15.1% | 54.9% | 48.6% |
| CrewAI | default | 18.2% | 53.3% | 51.3% |
| CrewAI | guardrail | 21.4% | 53.6% | 52.2% |
| AutoGen | default | 20.5% | 55.6% | 52.8% |
| AutoGen (Magentic-One) | guardrail | 8.3%† | **73.6%**§ | 55.6% |

‡ Strict injection-evidence floor: counts only flags quoting injection-only tokens.
It deliberately under-counts (it discards genuine paraphrase detections); the truth
lies between the floor and the published number, and **both should be quoted as a
pair**. The strict column is recomputable from committed code: `python
scripts/score_strict.py` regenerates
[STRICT-FLOOR.md](harness/runs/wave2/STRICT-FLOOR.md), which publishes the per-row
table and the persisted anchor classification with a reason for every anchor it
drops. Doing that recompute corrected the floors first published here by +1 to +3
cells on standard rows and -2 on Magentic
([QC ledger finding 5](harness/docs/qc-wave2-2026-07-24.md)); no headline moved.

† Same six wave-1
detections as the 4.0% in the wave-1 table above; the rate differs because the
denominator does — 150 valid wave-1 cells there, versus the 72 that survive wave-2's
pre-registered Magentic carve-out here. True detection in this row is ~0% either way
(wave-1 footnote 5).

§ **73.6% is
the honest number for this row, not the 84.7% in the scoreboard's union column** —
84.7% arises only under the permissive pre-registered mapping, whose Magentic acts are
100% stall noise ([footnotes 1–2](harness/runs/wave2/WAVE2-RESULTS.md)).

**The negative results carry equal prominence** (a pre-registered
publish-regardless commitment):

- **Reporting is not reacting.** Flag-only detections carry no corrective act.
  Recovery-without-detection falls from 51–61% to 26.1% on the union surface — but
  sits at **50.0% on the frozen wave-1 surface, essentially unchanged**. The protocol
  makes pipelines *report* what they were silently absorbing; it does not make them
  *act*. Notice-without-act does not disappear — it becomes legible.
- **No signal for silent model downgrades (O4).** Its flag rate (24.5%) *is* its
  clean-baseline false-anchor base rate (26.0%). The honest O4 number is the
  mapping-only 9.8%.
- **The intervention perturbs the instrument.** Magentic clean-run stall re-plans go
  3/25 seeds to 18/25 under the new output contract. Any protocol-level change to an
  orchestrator owes its readers that baseline comparison.
- **One at-ceiling cell class got worse**, violating prediction P2: a mandated report
  can anchor a reviewer into asserting the fault is absent, then approving.
- **Clean-baseline false-anchor base rates are published** (O1 32.7%, O4 26.0%,
  O5 24.0%, O3 12.7%, O2 5.3%, O6 1.3%). Any anchored-text detection metric owes
  readers this table; ours would have looked 23 points better on O4 without it.

Soft tier: judge kappa 0.767 over 68 double-judged pairs, zero exclusions; total
notice rate 65.5%, an 8.3-point override gap over the hard union.

### Uncertainty: what five replicates can and cannot support

Every number above is a point estimate over five repetitions of the whole matrix, and
cells within a repetition are correlated.
[UNCERTAINTY.md](harness/runs/wave2/UNCERTAINTY.md) puts intervals on all of them with
a replicate-cluster bootstrap, enumerating all 126 distinct resamples exactly rather
than simulating them. **The field named `seed` is a replicate label, not a random
seed** — the values 11–15 were never passed to the pipeline model or to any RNG (the
pre-registered [seeds file](seeds/wave2.json) already calls them "repetition
identifiers"), so this is a five-replicate sensitivity analysis, not a seeded
reproduction. Clustering on the replicate is earned by a real design feature: the
matrix driver caches one no-fault baseline run per (framework, config, task,
replicate) group and shares it across that group's cells.

The headline holds: median hard-tier detection **16.7% [15.6, 17.8] → 55.0%
[52.3, 58.0]**, a replicate-matched lift of **+38.3 pp [+36.4, +40.6]**; on the
726-cell same-cell paired grid the effect is **+39.4 pp [+37.0, +41.4]**, positive on
5/5 replicates in every framework row. Two things that file states plainly and the
tables above cannot: the five standard rows (53.3–55.6% published, 47.8–52.8% strict
floor) are **not distinguishable under this analysis** — every pairwise CI contains
zero, so this scoreboard is not yet a ranking — and a sign test on five replicates
can never reach p < 0.05 (exact minimum 0.0625). The O4 null is published there as a
single contrast rather than two overlapping intervals: fault runs minus clean
baselines on the anchored-flag surface is **−1.5 pp [−7.3, +4.0]**, and +1.4 pp
[−4.1, +6.3] once the denominators are matched — null either way, with the sign
unstable. None of that establishes equivalence; no equivalence margin was ever
pre-declared, and the file says so. Its limitations section is the point, not an
appendix: replicate resampling cannot cover model-version drift or task-suite
selection. Recompute with `python scripts/score_uncertainty.py --check`.

Full scoreboard, exclusion appendix, and all 9 QC footnotes:
[harness/runs/wave2/WAVE2-RESULTS.md](harness/runs/wave2/WAVE2-RESULTS.md).
Adversarial QC ledger — an internally independent 189/189 recompute (fresh code written
against the spec by a separate agent, same project and authorship — not third-party
external replication), the attack on the biggest lift claim, and the judge-sandbox
incident:
[harness/docs/qc-wave2-2026-07-24.md](harness/docs/qc-wave2-2026-07-24.md). Raw
traces for all 975 wave-2 runs and both quarantine directories are under
[harness/runs/](harness/runs/). Mutation-testing receipts:
[harness/MUTATION.md](harness/MUTATION.md). Spend ledger, including the wave-2
derivation and the caveat that the margined meter under-reads real billing:
[harness/SPEND.md](harness/SPEND.md).

## Add your framework to the scoreboard

Anyone can add a row, without the author's involvement. A submission is one scoreboard
row — one framework at one pinned version, one config, one pipeline model, over these
five tasks and six operators with at least five replicates — shipped as raw traces plus
a proposed [SPEC §5](SPEC.md#5-detection-act-mappings) detection-act mapping for that
framework, which is disputed publicly in the pull request before the row lands. You do
not compute your own numbers: `harness/scripts/validate_submission.py` recomputes every
claimed number from your traces using the scorers committed here and fails on a
one-cell disagreement, and CI runs it on every pull request. Scope is the deterministic
surfaces only — the mapping surface and the anchored-FLAGS union — because the
soft-tier judge cannot be replicated by a third party. Submitted rows are labelled
third-party and publish in a **separate table**: they are never pooled into the
author-run medians above and never enter the headline. The full route, the honesty bar
(publish-regardless, itemized exclusions, quarantine discipline), and what the
maintainer checks: **[SUBMITTING.md](SUBMITTING.md)**.

## Papers

- [papers/preprint-wave1.md](papers/preprint-wave1.md) — *Sabot: Do Multi-Agent
  Frameworks' Own Checks Detect Injected Faults?* (the 16.7% scoreboard)
- [papers/preprint-wave2.md](papers/preprint-wave2.md) — *The Checks Were Decorative
  — and the Fix Is Measurable* (the anomaly-first protocol)

## Standing on prior work

Sabot invents neither fault injection for agents nor agent-level mutation scoring. It is
a synthesis, measured comparatively at production scale: MAS-FIRE (arXiv 2602.19843)
established own-mechanism detection rates over injected faults on academic systems;
AgentAssay (arXiv 2603.02601) formalized an agent mutation score including model-swap
operators under external adjudication; AgentTelemetry (AIware 2026), AgentCollabBench
(arXiv 2605.08647), ReliabilityBench (arXiv 2601.06112), AutoInject (arXiv 2408.00989),
the "Failing Tools" benchmark (OpenReview j7YsSnA64D), and the chaos tools agent-chaos
and BalaganAgent occupy adjacent ground, credited in SPEC §9. What did not exist before
Sabot: a named comparative standard that separates
detected from reacted, attributes detection to named guardrail components, and publishes
framework-vs-framework results anyone can reproduce.

## Using the name, citing the work

- A number may be called a **Sabot Score** only if it was produced by a tagged SPEC
  revision, at that revision's pinned versions and configs, with the pre-registered
  seeds published in this repository. Anything else is "derived from Sabot" — say so.
- The canonical scoreboard lives in this repository. Maintainer disputes over mappings
  are adjudicated publicly here (SPEC §5).
- Archived and citable on Zenodo: [10.5281/zenodo.21539796](https://doi.org/10.5281/zenodo.21539796)
  (concept DOI, always the latest release). The `v0.2.0-wave2` release carrying both
  preprints and the full trace corpus is
  [10.5281/zenodo.21539797](https://doi.org/10.5281/zenodo.21539797).
- Cite via `CITATION.cff` (GitHub's "Cite this repository" button). Spec, docs, and
  results are CC BY 4.0 — attribution is required, not optional. Harness code
  publishes under Apache-2.0 with the results.

## Author

Jeff Otterson — [The Oracle Gate](https://github.com/Jott2121/oracle-gate) ·
[crucible](https://github.com/Jott2121/crucible)
