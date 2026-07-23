# Sabot

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
- Cite via `CITATION.cff` (GitHub's "Cite this repository" button). Spec, docs, and
  results are CC BY 4.0 — attribution is required, not optional. Harness code
  publishes under Apache-2.0 with the results.

## Author

Jeff Otterson — [The Oracle Gate](https://github.com/Jott2121/oracle-gate) ·
[crucible](https://github.com/Jott2121/crucible)
