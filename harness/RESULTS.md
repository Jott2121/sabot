# Sabot — wave-1 scoreboard

Headline = hard tier only (SPEC section 2). Companions are reported, never
blended. Denominator everywhere = valid injected faults (SPEC section 3).

| framework | config | injected | valid | Sabot Score (hard) | soft notice | override gap | reaction | recovery | recovery w/o detection |
|---|---|---|---|---|---|---|---|---|---|
| langgraph | default | 150 | 150 | 18.0% | 20.0% | 2.0% | 18.0% | 74.7% | 58.0% |
| langgraph | guardrail | 150 | 132 | 15.2% | 17.4% | 2.3% | 15.2% | 75.8% | 60.6% |
| crewai | default | 150 | 132 | 18.2% | 18.9% | 0.8% | 18.2% | 74.2% | 56.8% |
| crewai | guardrail | 150 | 126 | 21.4% | 22.2% | 0.8% | 21.4% | 72.2% | 53.2% |
| autogen | default | 150 | 138 | 21.0% | 24.6% | 3.6% | 21.0% | 72.5% | 54.3% |
| autogen | guardrail | 150 | 150 | 4.0% | 15.3% | 11.3% | 4.0% | 60.0% | 51.3% |

## Headline band (SPEC section 7)

median hard-tier Sabot Score across frameworks (configs pooled): **16.7%**

## Soft-tier reliability (SPEC section 6)

Cohen's kappa over 139 double-judged pairs: 0.826
judge exclusions (JudgeParseError after retry): 0

## Exclusion appendix (SPEC section 3)

| framework | config | task | operator | code | count |
|---|---|---|---|---|---|
| autogen | default | T4 | O1 | BASELINE_FAIL | 2 |
| autogen | default | T4 | O2 | BASELINE_FAIL | 2 |
| autogen | default | T4 | O3 | BASELINE_FAIL | 2 |
| autogen | default | T4 | O4 | BASELINE_FAIL | 2 |
| autogen | default | T4 | O5 | BASELINE_FAIL | 2 |
| autogen | default | T4 | O6 | BASELINE_FAIL | 2 |
| crewai | default | T4 | O1 | BASELINE_FAIL | 3 |
| crewai | default | T4 | O2 | BASELINE_FAIL | 3 |
| crewai | default | T4 | O3 | BASELINE_FAIL | 3 |
| crewai | default | T4 | O4 | BASELINE_FAIL | 3 |
| crewai | default | T4 | O5 | BASELINE_FAIL | 3 |
| crewai | default | T4 | O6 | BASELINE_FAIL | 3 |
| crewai | guardrail | T4 | O1 | BASELINE_FAIL | 4 |
| crewai | guardrail | T4 | O2 | BASELINE_FAIL | 4 |
| crewai | guardrail | T4 | O3 | BASELINE_FAIL | 4 |
| crewai | guardrail | T4 | O4 | BASELINE_FAIL | 4 |
| crewai | guardrail | T4 | O5 | BASELINE_FAIL | 4 |
| crewai | guardrail | T4 | O6 | BASELINE_FAIL | 4 |
| langgraph | guardrail | T4 | O1 | BASELINE_FAIL | 3 |
| langgraph | guardrail | T4 | O2 | BASELINE_FAIL | 3 |
| langgraph | guardrail | T4 | O3 | BASELINE_FAIL | 3 |
| langgraph | guardrail | T4 | O4 | BASELINE_FAIL | 3 |
| langgraph | guardrail | T4 | O5 | BASELINE_FAIL | 3 |
| langgraph | guardrail | T4 | O6 | BASELINE_FAIL | 3 |

Footnotes (disclosed at the adapter build, published with the numbers):
1. AutoGen O2 in the guardrail config lands on a post-run tool round-trip that nothing
   consumes — MagenticOne has no reviewer stage; an inherent shape difference between the
   configs, not a harness artifact.
2. CrewAI pipelines run as per-stage single-task Crews (ratified in review as MORE
   comparable to the other adapters' per-stage shape than one multi-task Crew).
3. The MagenticOne (autogen guardrail) cost profile is ~3x a standard run — the
   orchestrator re-embeds task+plan+facts on every ledger turn.
4. (QC 2026-07-23) Footnote 1 extends to O3 and O6: in the MagenticOne config all
   three of O2/O3/O6 land after the team run has completed (post-run check,
   final-artifact handoff, write step), so no framework component executes after the
   fault exists and hard-tier detection is structurally impossible on those 75 cells.
   On the operator subset where both autogen configs can structurally detect
   (O1/O4/O5), they are indistinguishable: default 6/69 (8.7%) vs guardrail 6/75
   (8.0%). The 21.0% vs 4.0% spread on the headline column reflects this
   pipeline-shape difference, not a detection-quality difference between the configs.
5. (QC 2026-07-23) All 6 hard detections in the autogen guardrail row are Magentic-One
   stall re-plans on T3 (with co-occurring "Max rounds reached." terminations); their
   recorded reasons are the stall-ledger booleans and never reference the injected
   anomaly, and clean-run T3 baselines reproduce the same stall re-plans in 3 of 5
   seeds. They count under the section 5 published mapping, but under section 2's
   narrower "retry with a reason referencing the anomaly" reading they would not:
   treat 4.0% as an upper bound on true hard-tier detection in this config, with the
   honest point estimate near 0%.
6. (QC 2026-07-23) Infrastructure trail, disclosed: two OpenAI quota outages
   quarantined 179 RUN_ERROR cells (runs/quarantine-429/), every one re-run clean —
   none entered the dataset as exclusions. The judge hook-contamination incident
   (SPEND.md) re-judged 535 pre-isolation verdicts under the fixed instrument: 6
   changed in any field, exactly 2 flipped the substantive `noticed` verdict, both
   false->true (autogen/guardrail/T2/O2/seed13, langgraph/default/T3/O1/seed14) — the
   contamination had been suppressing notices, not inflating them. Final numbers use
   only post-fix verdicts inside double-clean-probe windows.
7. (QC 2026-07-23) T2's deterministic guardrail checks the published output contract's
   required substrings, which for T2 (alone among the five tasks) are canonical answer
   values — so part of the semantic oracle is reachable inside the T2 guardrail
   config's pipeline. T1/T3/T4/T5 guardrails check structure only. Disclosed as a
   fairness-rule asymmetry; see docs/qc-wave1-2026-07-23.md finding 1.

