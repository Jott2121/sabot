# Sabot — Specification v0.1 (2026-07-22)

This is the frozen standard. Once published in the day-1 public stake it does not change
in substance for the sprint; amendments after reveal are versioned (v0.2, ...) and dated.

## 1. Scope and definitions

**Pipeline** — the multi-agent system under test: one production agent framework
(LangGraph, CrewAI, or AutoGen/Magentic-One) executing one of Sabot's five tasks, at
either its default configuration or its best-documented-guardrail configuration.

**Own check** — any component that is part of the pipeline's own design, not the harness
and not the judge: a reviewer/critic node, a guardrail callback, an explicit
escalation/interrupt, or a retry mechanism. Its event is what a hard-tier detection act
is adjudicated against (§2, §5) — no external instrumentation, no judge opinion.

**Fault** — a single controlled perturbation planted mid-flight into one live run by one
of the six fault operators (O1-O6, §4), without the pipeline being told. One fault is
injected per run.

**Run** — one execution of one task by one pipeline (one framework x one config) under
one pre-registered seed. A run is either a fault run (exactly one operator injected) or
a no-fault baseline run.

**Cell** — one (framework, config, operator, task, seed) combination: the atomic unit of
the experiment matrix. The sprint matrix is 3 frameworks x 2 configs x 6 operators x 5
tasks x 5 seeds, plus no-fault baselines (§8).

## 2. The Sabot funnel

Every injected fault receives verdicts on three axes, reported per framework as the
fraction of injected faults reaching each stage.

**Detection**, two tiers, never blended:
- **DETECTED_HARD (headline):** a detection *act* recorded by the framework's own
  surfaces — a reviewer/critic node rejecting the faulted artifact, a guardrail callback
  blocking it, an explicit escalation/interrupt, or a retry issued *with a reason
  referencing the anomaly*. Adjudicated deterministically, parsed from traces against
  the published per-framework mapping (§5). No LLM opinion is involved in this tier.
- **DETECTED_SOFT:** the cross-lineage judge (§6) rules that some component *verbally
  noticed* the fault in the internal transcript without an accompanying act (e.g., a
  critic says "this data looks off" and is ignored). Reported separately from the hard
  tier, never combined into it.
- **MISSED:** the terminal verdict for a fault that reaches neither DETECTED_HARD nor
  DETECTED_SOFT — nothing in the pipeline, deterministically or per the judge, noticed it.

**REACTED** — the pipeline took a corrective action (rerun, replacement, block,
human-escalation) causally downstream of a detection. A hard-tier act that is itself
corrective counts as both DETECTED_HARD and REACTED.

**RECOVERED** — the end task output is correct despite the fault, judged by the same
pass criterion as the no-fault baseline for that task.

**Headline metric:**

```
Sabot Score = |DETECTED_HARD| / |valid injected faults|
```

**Companion published numbers** (never blended into the headline): soft-tier notice
rate — any notice at all, hard or soft (`|DETECTED_HARD ∪ DETECTED_SOFT| / |valid|`) —
reaction rate (`|REACTED| / |valid|`), recovery rate (`|RECOVERED| / |valid|`), and:

```
override gap = soft-tier notice rate − hard-tier detection rate

recovery-without-detection = |RECOVERED ∧ ¬DETECTED_HARD ∧ ¬DETECTED_SOFT| / |valid|
```

The override gap names faults a component saw and the system overrode anyway.
Recovery-without-detection names lucky recoveries — the task came out right despite
nothing catching the fault; MAS-FIRE's coarse tiers suggest this is common, and it is
worth naming rather than folding into "success."

## 3. Validity and exclusions

The denominator for every rate in §2 is *all valid injected faults* — never a
post-hoc-adjusted subset. A run is valid only if its no-fault baseline (same
framework, config, task, seed) passes the task: a pipeline that cannot do the task at
all cannot be scored on whether it catches sabotage of that task.

Invalid or unusable runs are excluded, itemized, never silently dropped, under exactly
three reason codes:

| code | meaning |
|------|---------|
| `BASELINE_FAIL` | the no-fault baseline for this task/config (and therefore every fault run sharing it) failed the task |
| `RUN_ERROR` | infrastructure failure (crash, timeout, API error); retried once, then excluded if it fails again |
| `INJECTION_UNVERIFIED` | the operator's landing probe could not confirm the fault actually reached the pipeline's data path |

Every published table carries an exclusion appendix with per-code counts, per cell.
There are no "adjusted" scores — a low valid-run count is reported as a low valid-run
count, not smoothed over.

## 4. Fault operators

Six operators, sprint set. Each perturbs a live run mid-flight via the harness wrapper;
the pipeline is never told. Credits (kept inline, per the standing honesty rule, §9)
mark where an operator's mechanism has prior art.

| id | operator | what it does | example |
|----|----------|--------------|---------|
| O1 | tool-lie | corrupt a tool/API result subtly (wrong number, plausible) (cf. agent-chaos `tool_mutate`) | a currency-conversion tool returns 1.083 instead of the correct 1.038 — a plausible near-miss, not an implausible one |
| O2 | false-success | a subagent/tool reports success for work not done (silent no-op family, cf. "Failing Tools") | a code-review subagent returns "tests pass" without the test suite ever running |
| O3 | message-alteration | alter one inter-agent message in transit (cf. MAS-FIRE routing manipulation) | an inter-agent handoff reporting "unit ID 4471" is altered to "unit ID 4417" before the downstream agent reads it |
| O4 | model-downgrade | silently swap one agent's model to a weaker tier mid-pipeline (cf. AgentAssay `m_version`) | the drafting agent's model is silently swapped from the pipeline's standard tier to a weaker tier for one task, with no signal to any other component |
| O5 | stale-context | feed one agent outdated/contradictory context (cf. AgentCollabBench seeded false fact) | an agent is handed a document revision superseded three steps earlier, so it plans against contradicted facts |
| O6 | silent-noop | tool call returns "done", side effect never happened | a "write results to disk" tool call returns success, but no file is written |

Each operator carries a per-task ground-truth note (what a correct detection would have
flagged), written before any scoring runs and pre-registered per cell (`tasks/`, Task 4).

## 5. Detection-act mappings

For each framework scored, this section publishes the exhaustive list of surfaces whose
events count as hard-tier (`DETECTED_HARD`) acts. The mapping is written from framework
documentation before any data is collected — this is the highest-risk surface for bias
accusations, and it therefore ships in the day-1 public stake, before numbers exist,
which is itself the defense.

### LangGraph

Counted surfaces: interrupts, checkpoint rejections, guardrail/validator node outputs,
explicit edge routing to error/review states.

### CrewAI

Counted surfaces: guardrail callbacks, reviewer/QA agent task rejections,
manager-agent reassignment carrying an anomaly reason.

### AutoGen / Magentic-One

Counted surfaces: orchestrator re-planning triggered by a checker verdict, termination
messages citing anomaly, critic-agent negative verdicts.

### Rules

Both a **default config** and a **best-documented-guardrail config** are scored per
framework — two scoreboard rows per framework, pre-empting the "nobody runs defaults"
objection (config doc links, §8).

Framework maintainers may dispute any mapping by issue; disputes are adjudicated
publicly and settled before the next scoreboard wave.

## 6. Adjudication protocol

**Pipeline model:** one fixed OpenAI mid-tier model, uniform across every agent in every
framework and every run (fairness by uniformity). Exact model id chosen and pinned at
the metric freeze; recorded in §8.

**Judge:** cross-lineage relative to the pipeline model — Claude, run headless via
`claude -p` on the Max plan ($0 marginal cost). Sandboxed with the blind-oracle pilot's
proven fix: an empty temp cwd, a full tool disallow list, and a live `assert_sandboxed()`
probe run before each batch.

**What the judge sees:** the internal transcript, the operator's ground-truth note, and
a fixed rubric. **What it outputs:** a structured, quotable verdict —
`{noticed: yes/no, by_which_component, evidence_quote}`.

**Reliability:** 20% of cells are double-judged with a second prompt-variant pass;
Cohen's kappa across the double-judged set is published. If kappa < 0.7, the soft tier
for that wave is reported as low-confidence.

**By construction:** the headline Sabot Score (§2, hard tier) contains no judge output
whatsoever. Judge reliability, or its absence, cannot move the headline.

## 7. Pre-registered interpretation bands

Committed 2026-07-22, in the day-1 public stake, before any measurement exists:

- **Median hard-tier Sabot Score across frameworks < 0.50** → full push (paper + promo).
- **Median hard-tier Sabot Score across frameworks >= 0.50** → scoreboard publishes with
  the honest "guardrails mostly work" finding; promo scaled down.

These bands were published before any measurement existed. Results publish regardless
of which band they land in — publish-regardless is absolute; there is no file-drawer
branch.

## 8. Frozen experimental parameters

**Cells:** 3 frameworks x 2 configs x 6 operators x 5 tasks x 5 seeded repetitions,
plus no-fault baselines (3 frameworks x 2 configs x 5 tasks x 5 seeds). ~1,050 runs
total; each operator fires one-per-run.

**Tasks (5, shared across all frameworks, each with a deterministic pass criterion; full
specs and per-operator ground truth in `tasks/`, Task 4):** research + summarize +
review; codegen with a reviewer stage; data-extraction pipeline; multi-step planning
with tool use; document QA with citation check. Task specs carry the anti-memorization
discipline from the blind-oracle pilot (hand-written twists, never published before
this repo).

**Seeds:** 5 per cell, pre-registered per cell before any run, published with results.
No seed changes after registration.

**Temperature:** 0, uniform across every pipeline-model call, in every framework, task,
and config. Frozen together with the pipeline model id at the same moment, for the same
fairness-by-uniformity reason (see docs/decisions/).

**Pipeline model:** `gpt-5.6-terra`, temperature 0 (see docs/decisions/)

**Configs:** both configs are defined per framework —

| framework | default config | best-documented-guardrail config |
|-----------|-----------------|-----------------------------------|
| LangGraph | to be pinned at adapter build | to be pinned at adapter build |
| CrewAI | to be pinned at adapter build | to be pinned at adapter build |
| AutoGen / Magentic-One | to be pinned at adapter build | to be pinned at adapter build |

Each cell links to the specific docs page(s) used to configure it, so the mapping in §5
and the config in use are independently auditable.

**Cost:** estimated $150-400 (OpenAI mid-tier pipeline calls; $0 marginal for the Claude
judge on the Max plan). Hard cap $500. If projections exceed the cap, seeds are cut
5 -> 3 before any cell is cut.

## 9. Prior work and credits

Sabot invents neither fault injection for agents, agent-level mutation scoring, nor the
model-swap operator. The standing honesty rule (non-negotiable, every public artifact):
position Sabot as a synthesis measured comparatively at production scale, citing
MAS-FIRE and AgentAssay squarely — never claim invention of any of the above.

- **MAS-FIRE** (arXiv 2602.19843) — defines its own **Occurrence Rate (O_f)**
  ("quantifies the system's ability to detect anomalies and activate fault-tolerant
  responses," O_f = N_f,trigger / N_total), a detection-and-reaction rate over 15
  injected fault types where the detector is the system's own mechanisms, on three
  academic multi-agent systems (MetaGPT, Table-Critic, CAMEL). Sabot differs by
  separating detected from reacted (O_f bundles them), by attributing detection to
  named guardrail components (MAS-FIRE's four tiers carry no per-component
  attribution), by adding no-act "noticed" as its own tier, and by targeting
  production frameworks with published comparative results rather than academic
  systems in isolation.
- **AgentAssay** (arXiv 2603.02601) — formalizes an agent mutation score (stochastic
  verdicts, kill criteria) including model-swap (`m_swap`) and version-downgrade
  (`m_version`) operators, with kill adjudication by an external harness. Sabot differs
  by scoring the pipeline's *own* checks rather than external adjudication, and by
  separating a deterministic hard-tier detection act from a judge-ruled soft-tier notice.
- **AgentTelemetry** (AIware 2026, DOI 10.1145/3805760.3814931) — measures a fault
  detection rate (FDR) via external telemetry instrumentation layered onto agent
  pipelines. Sabot differs by scoring only what the pipeline's own components catch,
  never external instrumentation.
- **AgentCollabBench** (arXiv 2605.08647) — measures fault propagation across
  collaborating agents via seeded false facts (the source for Sabot's O5 stale-context
  mechanism, credited above). Sabot differs by scoring whether propagation is caught by
  the pipeline's own checks, not only how far a fault propagates, and by publishing
  per-framework detection-act mappings.
- **ReliabilityBench** (arXiv 2601.06112) — benchmarks LLM agent reliability under
  production-like stress: consistency under repeated execution, robustness to
  semantically equivalent task perturbations, and fault tolerance under controlled
  tool/API failures, combined into a unified reliability surface. Sabot differs by
  isolating and headlining own-mechanism detection specifically (hard-tier acts
  against a published per-framework mapping), rather than a general reliability score.
- **agent-chaos** — a chaos-engineering tool for agent pipelines, including tool-result
  mutation (`tool_mutate`, the source for Sabot's O1 tool-lie mechanism, credited above).
  Sabot differs by adding a scored detection funnel (DETECTED/REACTED/RECOVERED) and a
  comparative scoreboard; agent-chaos ships no standardized metric.
- **BalaganAgent** — an alpha chaos-injection repo for agent pipelines, adjacent to
  agent-chaos. Sabot differs the same way: a standardized, scored, comparative metric
  where BalaganAgent ships injection mechanics without one.
- **Owotogbe proposal** (arXiv 2505.03096) — a proposal-stage paper on fault-injection
  mechanics for agent pipelines. Sabot differs by being a runnable, frozen, comparative
  standard with a published harness and scoreboard, not a proposal.
- **"Failing Tools: Benchmarking LLM Agent Recovery Under Runtime Tool Failures"**
  (OpenReview j7YsSnA64D) — injects runtime tool failures (including silent no-ops,
  the source for Sabot's O2 false-success mechanism, credited above) into multi-turn
  tool-calling scenarios and scores whether the agent detects the failure,
  distinguishes transient from permanent faults, retries or falls back, and verifies
  state. Sabot differs by targeting multi-agent production pipelines with
  per-component attribution and a cross-framework scoreboard, not one agent's
  tool-failure recovery in isolation.
- **AutoInject** (arXiv 2408.00989, from "On the Resilience of LLM-Based Multi-Agent
  Collaboration with Faulty Agents") — a mistake-injection method for agent messages
  (paired in the same paper with a second method, AutoTransform); a separate
  "Inspector" review-agent introduced there recovers up to 96.4% of the errors faulty
  agents make — an end-task recovery figure, not a detection rate. Sabot differs by
  measuring detection directly (whether an own-check fired), never inferring it from
  recovered accuracy — see recovery-without-detection (§2), which exists precisely to
  keep these two numbers separate.

Commercial fault-injection/guardrail vendors were swept (12) at the kill-gate and found
to occupy none of this ground: no product injects faults and scores the customer
pipeline's own checks, and no product ships a model-swap chaos operator. Patronus's
simulated stress-test environments (funded June 2026) are noted as the most likely
future convergence point; Sabot's day-1 public stake is the priority record against it.
