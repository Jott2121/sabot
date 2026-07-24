# Sabot

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21539796.svg)](https://doi.org/10.5281/zenodo.21539796)

**Crash-test ratings for agent stacks.** Sabot plants controlled faults inside a running
agent pipeline and scores what fraction of them the pipeline's **own** checks catch.

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
| LangGraph | default | 17.4% | 55.1% | 47.1% |
| LangGraph | guardrail | 15.1% | 54.9% | 47.9% |
| CrewAI | default | 18.2% | 53.3% | 50.7% |
| CrewAI | guardrail | 21.4% | 53.6% | 50.0% |
| AutoGen | default | 20.5% | 55.6% | 52.1% |
| AutoGen (Magentic-One) | guardrail | 8.3%† | **73.6%**§ | 58.3% |

‡ Strict injection-evidence floor: counts only flags quoting injection-only tokens.
It deliberately under-counts (it discards genuine paraphrase detections); the truth
lies between the floor and the published number, and **both should be quoted as a
pair**. The strict column is currently a stated QC-pass result rather than a
committed code path; making it independently reproducible is the first v0.2.1 item
([QC ledger finding 5](harness/docs/qc-wave2-2026-07-24.md)). † Same six wave-1
detections as the 4.0% in the wave-1 table above; the rate differs because the
denominator does — 150 valid wave-1 cells there, versus the 72 that survive wave-2's
pre-registered Magentic carve-out here. True detection in this row is ~0% either way
(wave-1 footnote 5). § **73.6% is
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

Full scoreboard, exclusion appendix, and all 9 QC footnotes:
[harness/runs/wave2/WAVE2-RESULTS.md](harness/runs/wave2/WAVE2-RESULTS.md).
Adversarial QC ledger — an independent 189/189 recompute, the attack on the biggest
lift claim, and the judge-sandbox incident:
[harness/docs/qc-wave2-2026-07-24.md](harness/docs/qc-wave2-2026-07-24.md). Raw
traces for all 975 wave-2 runs and both quarantine directories are under
[harness/runs/](harness/runs/). Mutation-testing receipts:
[harness/MUTATION.md](harness/MUTATION.md). Spend ledger, including the wave-2
derivation and the caveat that the margined meter under-reads real billing:
[harness/SPEND.md](harness/SPEND.md).

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
