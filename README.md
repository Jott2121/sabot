# Sabot

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21539796.svg)](https://doi.org/10.5281/zenodo.21539796)
[![License: CC BY 4.0](https://img.shields.io/badge/spec%20%26%20results-CC%20BY%204.0-blue.svg)](LICENSE)
[![Harness: Apache 2.0](https://img.shields.io/badge/harness-Apache%202.0-blue.svg)](LICENSE-CODE)
[![SPEC](https://img.shields.io/badge/SPEC-v0.2.1-informational.svg)](SPEC.md)

**What the reviewers in agent pipelines actually catch.** Sabot plants controlled faults
inside running multi-agent pipelines and scores whether the pipeline's **own** reviewer
and guardrail stages flag them, act on them, or miss them.

> **The findings.** Measured on LangGraph, CrewAI and AutoGen/Magentic-One, with every
> detection adjudicated deterministically:
>
> 1. **An action that never happened is invisible.** When a write tool reported success
>    but wrote nothing, no reviewer flagged it and the task failed in every valid cell:
>    **0 of 119 flagged, 0 of 119 correct**, on all three frameworks. Reviewers judge
>    text, and a missing side effect leaves nothing in the text to quote.
> 2. **Faults in the text get noticed; faults in the process mostly do not.** Once
>    reviewers had to report what they noticed before ruling, a wrong value in a tool
>    result was flagged in **92.4%** of cells, an altered handoff in 88.2%, and a stale,
>    superseded document in 87.4%. A silently skipped review step was flagged in
>    **31.9%**, and a silently downgraded model in 26.9%. Counting only the anchored
>    flags, the O4 rate is 22.7%, below the 24.8% at which that same rule fires on
>    clean runs: no detection signal at all.
> 3. **Noticing is not acting.** A wrong tool value was flagged in 92.4% of cells but
>    met with a corrective act (a reject, retry, block or escalation) in **40.3%**, and
>    37.8% of cells flagged the wrong value and still ended with the wrong answer.
>
> The change behind those numbers is one requirement added to the reviewer prompt:
> report every inconsistency you noticed, quoting the values, *before* you rule. It
> raised median detection from **16.7%** to **55.0%** on the same 825 paired cells. It
> made the noticing legible. It did not make pipelines act on it.
>
> Spec and anchors were registered publicly **before any scored run**. Negative
> results publish at equal prominence. [Findings by fault type](#the-findings-by-fault-type) ·
> [Wave-1 results](#wave-1-results-2026-07-23) ·
> [Wave-2 results](#wave-2-results-2026-07-24-the-fix-measured) · [Papers](papers/) ·
> [Limitations](#wave-2-results-2026-07-24-the-fix-measured)

**What is being measured.** Teams building on agent frameworks add self-verification:
reviewer agents, critic stages, guardrail callbacks. Sabot measures what those checks
catch, in reference pipelines it builds on each framework from that framework's
documented surfaces: a reviewer agent that ends with a verdict token, plus the
framework's best-documented guardrail mechanism in the guardrail configuration (for
AutoGen, the Magentic-One orchestrator, which has no reviewer). The reviewer instructions
Sabot writes are **byte-identical across all three frameworks** for every task, with each
framework wrapping them in its own agent scaffolding, and every cell runs one pipeline
model (`gpt-5.6-terra`) at pinned framework versions. So these are results
about this reviewer design with this model. The three frameworks show the pattern holds
across orchestrators: the five reviewer-bearing rows all land between 53% and 56% on
wave-2 detection. They are not a ranking of frameworks (see
[Uncertainty](#uncertainty-what-five-replicates-can-and-cannot-support)), and they are
not laws of nature.

Sabot is a standard (a frozen metric spec), a harness (a runnable tool), and a public
scoreboard.

## The findings by fault type

The six fault operators are different kinds of fault, and a single median across them
hides that. Wave-2 cells on the five reviewer-bearing rows, regrouped by operator; no
number is rescored:

| fault (operator) | flagged | anchored only | clean-run false-flag | acted on | answer still right |
|---|---:|---:|---:|---:|---:|
| O6 write reports success, writes nothing | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| O1 tool returns a wrong value | 92.4% | 92.4% | 29.6% | 40.3% | 58.0% |
| O3 handoff message altered | 88.2% | 87.4% | 12.0% | 85.7% | 94.1% |
| O5 stale document labeled superseded | 87.4% | 87.4% | 19.2% | 0.8% | 100.0% |
| O2 review step silently skipped | 31.9% | 31.1% | 6.4% | 13.4% | 94.1% |
| O4 worker model silently downgraded | 26.9% | 22.7% | 24.8% | 11.8% | 96.6% |

119 valid cells per operator. *Flagged* is the wave-2 hard-tier union surface (the
frozen wave-1 mapping or an anchored FLAGS line). *Anchored only* is the FLAGS half by
itself, and *clean-run false-flag* is the rate at which that anchored rule fires on a
clean baseline with no fault present, so compare those two. For O4 the anchored rate
sits below its clean rate: no detection signal. *Acted on* is a corrective act (a
reported flag alone does not count).
For O5, a low acted-on rate is the right outcome: the answer was correct in every cell,
so a rejection would have been wrong.

**What recovery-without-detection does and does not show.** The earlier headline, a
correct final answer with nothing flagging the fault, is real, but in wave 2 it is
concentrated in O2 and O4: they account for 165 of the 194 such cells (85.1%), and in
the cells where nothing was flagged, their answers were right 100% (O2, 81 of 81) and
96.6% (O4, 84 of 87) of the time. For those faults the outcome cannot distinguish a
check that failed from a fault that never changed the answer. Separating the two needs a control arm that injects the fault with
the reviewer disabled, which neither wave ran.

Full table with counts, and the population definition: [BY-OPERATOR.md](harness/runs/wave2/BY-OPERATOR.md).
Recompute it offline, and verify it against its frozen baseline:
`python scripts/score_by_operator.py --check` (from `harness/`).

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
- **2026-09-25:** README reorganized around the results by fault type, and its framing
  corrected: the reviewer stages are Sabot's reference pipelines, with identical prompts
  across frameworks, not reviewers the frameworks ship. No number was rescored; SPEC and
  papers are unchanged. New `scripts/score_by_operator.py` regenerates the by-operator
  table from the published rows and is checked in CI.

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
  Frameworks' Own Checks Detect Injected Faults?* (the 16.7% scoreboard). The papers are
  left as published; for what the reviewer stages are, read "What is being measured"
  at the top of this README rather than the title.
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
