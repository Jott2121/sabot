# Sabot — Specification v0.1.1 (2026-07-22)

*Base v0.1 frozen 2026-07-22; amended to v0.1.1 the same day — pre-data adapter-build
amendments touching only §5 and §8. The metric core (§1-§4, §6, §7, §9) is unchanged.
See the Amendment log at the end of this document.*

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
flagged), written before any scoring runs and pre-registered per cell (`tasks/`).

## 5. Detection-act mappings

For each framework scored, this section publishes the exhaustive list of surfaces whose
events count as hard-tier (`DETECTED_HARD`) acts. The mapping is written from framework
documentation before any data is collected — this is the highest-risk surface for bias
accusations, and it therefore ships in the day-1 public stake, before numbers exist,
which is itself the defense.

### LangGraph

Counted surfaces (v0.1.1): **interrupts** (`langgraph.types.interrupt`, observed via the
`__interrupt__` key in the `.invoke()` result), **validator/guardrail node outputs**, and
**explicit error/review routing** (`Command(goto=...)`).

> **v0.1.1 (2026-07-22):** "checkpoint rejections" removed from the LangGraph counted
> surfaces — it does not exist as an API concept in langgraph 1.2.9 (confirmed absent from
> the persistence docs; evidence pack `docs/framework-docs-2026-07-22/langgraph.md`).
> Publishing a counted surface that cannot fire is worse for the bias-accusation defense
> than removing it pre-data, so it is struck.

Per-act mapping (act → mechanism, from the adapter build):

| act | mechanism |
|-----|-----------|
| reject (reviewer) | reviewer LLM output parsed `VERDICT: REJECT` via the verdict-token protocol |
| reject (validator) | deterministic `validate` node routes `Command(goto="revise")` on the first output-contract failure (guardrail config) |
| retry_with_reason | the revise loop re-invokes the worker carrying the rejection reason |
| escalate | a second validator failure calls `langgraph.types.interrupt(reason)`, observed via the `__interrupt__` result key; the run terminates with the task recorded as failed |

### CrewAI

Counted surfaces (v0.1.1): **task guardrail callbacks** returning `(False, reason)`,
including LLM guardrails (observed via `LLMGuardrailCompletedEvent(success=False)` in crewai
1.15.5); **reviewer/QA agent task rejections** via the verdict-token protocol.

> **v0.1.1 (2026-07-22):** "manager-agent reassignment carrying an anomaly reason" moved to
> the **soft tier** — crewai 1.15.5 emits no structured anomaly-reason event; hierarchical
> delegation is an ordinary tool call (`DelegateWorkTool`) whose reason lives only in the
> manager LLM's free text, so it cannot be adjudicated deterministically. It therefore
> cannot be a hard-tier act; a judge may still rule it a soft-tier notice. Separately, the
> event named in early docs, `LLMGuardrailFailedEvent`, **does not exist** in the installed
> 1.15.5 release; `LLMGuardrailCompletedEvent(success=False)` is the equivalent reject
> signal and is what the mapping uses.

Per-act mapping (act → mechanism, from the adapter build):

| act | mechanism |
|-----|-----------|
| reject (reviewer) | reviewer stage-Crew output parsed `VERDICT: REJECT` via the verdict-token protocol |
| reject (guardrail) | LLM-guardrail failure surfaced as `LLMGuardrailCompletedEvent(success=False)` (guardrail config) |
| retry_with_reason | a guardrail failure with `retry_count < guardrail_max_retries` (the framework will retry) |
| escalate | `guardrail_max_retries` exhausted → crewai's own terminal exception (matched by its exact message pattern); the run completes with the task recorded as failed |

### AutoGen / Magentic-One

Counted surfaces (v0.1.1): **critic-agent negative verdicts** via the verdict-token
protocol; **termination messages citing anomaly** (regex over `TaskResult.stop_reason`:
contains `VERDICT: REJECT`, or equals the 0.7.5 exhaustion message `Max rounds reached.`);
**orchestrator re-planning** — the Magentic-One stall re-plan, adjudicated from the
framework's own trace-logger progress-ledger record and the exact 0.7.5 log line
`Stall count exceeded, re-planning with the outer loop...`.

> **v0.1.1 (2026-07-22):** the re-plan and termination surfaces are restated with the exact
> mechanisms of the pinned autogen-agentchat 0.7.5. In 0.7.5 a Magentic-One stall does NOT
> terminate the run — it re-plans (rebuilds the task ledger, re-enters the outer loop) and
> the group chat continues; the re-plan is observable ONLY via the trace-logger hook, never
> via `stop_reason`. `stop_reason` carries an anomaly only when a critic `VERDICT: REJECT`
> propagates to termination, or on the max-turns exhaustion phrase `Max rounds reached.`

Per-act mapping (act → mechanism, from the adapter build):

| act | mechanism |
|-----|-----------|
| reject (critic) | critic `TextMessage` parsed `VERDICT: REJECT` via the verdict-token protocol (default config) |
| retry_with_reason | the revise loop re-dispatches the worker with the reject reason; OR the Magentic-One re-plan, recorded from the trace-logger progress-ledger record (guardrail config) |
| block | `TaskResult.stop_reason` matches `VERDICT: REJECT` or `Max rounds reached.` (guardrail config) |

### Verdict-token protocol (all frameworks)

Every reviewer/critic LLM component adjudicated in the hard tier uses one published
protocol. The prompt requires the reply to **end with exactly one line**:

```
VERDICT: APPROVE
```

or

```
VERDICT: REJECT - <reason>
```

Parse rule (case-insensitive, first match):

```
VERDICT:\s*(APPROVE|REJECT)\s*(?:-\s*(.*))?
```

**No token = no hard-tier act.** A reviewer that merely comments without emitting the
token produces nothing at the hard tier — that is the soft tier's territory (§2, §6).

**Guardrail-retry exhaustion = escalate.** CrewAI's own terminal exception after
`guardrail_max_retries` is scored as **escalate** — a hard-tier detection act, with the run
completed and the task recorded as failed — mirroring LangGraph's validator
escalate-via-`interrupt()`. It is **never** excluded as `RUN_ERROR`: the reject/retry acts
already recorded during the retry loop are real own-check activity and must not be erased.

### Fairness rule (deterministic guardrail/validator code) — §5 and §8

Any deterministic guardrail or validator code that runs inside a pipeline may implement
**only the task's published output contract** — never an operator-specific fault oracle. The
semantic pass/fail oracle that decides whether a planted fault was actually caught lives
**only in the scorer**, never in the pipeline. Stated once here; it governs the §5 mappings
and the §8 configs alike.

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
specs and per-operator ground truth in `tasks/`):** research + summarize +
review; codegen with a reviewer stage; data-extraction pipeline; multi-step planning
with tool use; document QA with citation check. Task specs carry the anti-memorization
discipline from the blind-oracle pilot (hand-written twists, never published before
this repo).

**Seeds:** 5 per cell, pre-registered per cell before any run, published with results.
No seed changes after registration.

**Temperature (corrected v0.1.1, 2026-07-22):** no temperature parameter is transmitted by
any adapter; every pipeline-model call runs at the model's own default temperature,
uniformly across every framework, task, and config. The original v0.1 wording
("temperature 0") is **corrected**: `gpt-5.6-terra` accepts only its default temperature — an
explicit `temperature=0` is rejected with an HTTP 400 on the raw Chat Completions path
("Unsupported value: 'temperature' does not support 0 with this model. Only the default (1)
value is supported"), and langchain-openai silently strips `temperature` for gpt-5* models.
Both facts were verified live during the adapter build (2026-07-22; see
docs/decisions/2026-07-22-adapter-config-pins.md). Fairness-by-uniformity is preserved — the
knob does not exist on this model, so every call is uniform at the default by construction.

**Pipeline model:** `gpt-5.6-terra`, at the model's default temperature (see the Temperature
correction above; docs/decisions/2026-07-22-pipeline-model-pin.md and
docs/decisions/2026-07-22-adapter-config-pins.md).

**O4 model-downgrade target (pinned v0.1.1):** `gpt-5.6-luna` — the same-generation next rung
down the current OpenAI Frontier ladder from the pipeline model `gpt-5.6-terra` ($1.00/$6.00
vs. $2.50/$15.00 per 1M tokens; described "optimized for cost-sensitive workloads"). Chosen
over `gpt-5.4-mini` / `gpt-5.4-nano` (previous-generation SKUs) so the downgrade stays inside
one model family and O4 measures tier-downgrade detection, not a generation swap. Lineup
live-checked 2026-07-22 against `developers.openai.com/api/docs/models` and `.../pricing`;
candidates and rationale in docs/decisions/2026-07-22-adapter-config-pins.md.

**Configs (pinned v0.1.1, 2026-07-22):** both configs are defined per framework, at the exact
pinned versions below. Every pipeline is a hand-rolled multi-agent shape (load → worker →
review → revise/emit); the two configs differ only in the review/guardrail machinery.

| framework (pinned versions) | default config | best-documented-guardrail config |
|-----------|-----------------|-----------------------------------|
| **LangGraph** — `langgraph==1.2.9`, `langchain-openai==1.4.0` | hand-rolled `StateGraph` pipeline (`load → worker → review → (revise \| emit)`); `review` is an LLM reviewer using the verdict-token protocol; one revise loop | adds a deterministic `validate` node between review-approve and emit, checking **only** the published output contract; first failure routes `Command(goto="revise")`, a second calls `langgraph.types.interrupt()` (escalate) |
| **CrewAI** — `crewai==1.15.5` | sequential per-stage `Crew(process=Process.sequential)` — a worker Agent/Task then a reviewer Agent/Task using the verdict-token protocol; no task guardrail | worker `Task(guardrails=[<deterministic output-contract check>, <LLM guardrail>], guardrail_max_retries=3)` retry loop (reject via a guardrail returning `(False, reason)` / `LLMGuardrailCompletedEvent(success=False)`, escalate on exhaustion) plus the reviewer stage |
| **AutoGen / Magentic-One** — `autogen-agentchat==0.7.5`, `autogen-core==0.7.5`, `autogen-ext[openai]==0.7.5` | per-stage `RoundRobinGroupChat([agent], TextMentionTermination)` — a worker turn then a critic turn using the verdict-token protocol | `MagenticOneGroupChat(max_stalls=3)` — the orchestrator's internal LLM progress-ledger IS the review mechanism; re-plan observed via the trace-logger, anomaly termination via `stop_reason` |

Doc links (the specific pages used to configure each, so the §5 mapping and the config in use
are independently auditable): LangGraph — `docs.langchain.com/oss/python/langgraph/interrupts`,
`.../graph-api`, `.../streaming`; CrewAI — `docs.crewai.com/en/concepts/tasks`,
`.../event-listener`; AutoGen — `microsoft.github.io/autogen` (0.7.5 stable). Full evidence in
`docs/framework-docs-2026-07-22/{langgraph,crewai,autogen}.md`.

**AutoGen lineage note (honest disclosure).** `autogen-agentchat` is pinned at 0.7.5, its last
release (2025-09-30); the AutoGen line is in **maintenance mode**. It is pinned deliberately: a
frozen API is reproducible, and 0.7.5 is the only lineage with doc-verified Magentic-One ledger
internals, which §5's "AutoGen / Magentic-One" surfaces require. Microsoft's active successor,
`agent-framework` (1.0 GA 2026-04-02; **1.12.0** released 2026-07-21), is the named **wave-2
candidate** — deferred here only because its Magentic-observability depth is an open research
gap at freeze time, not because it is unavailable.

| lineage | status | version pinned / candidate | scoreboard wave |
|---------|--------|----------------------------|-----------------|
| AutoGen / Magentic-One (`autogen-agentchat`) | maintenance mode (last release 2025-09-30) | `0.7.5` (pinned) | wave 1 (this sprint) |
| Microsoft `agent-framework` | active (1.12.0, 2026-07-21) | `1.12.0` (candidate) | wave 2 (Magentic observability to be verified first) |

Config pins land as a dated v0.1.x amendment before any scored run; no scoreboard result may
cite a config that is not pinned in a tagged SPEC revision.

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

## Amendment log

### v0.1.1 — 2026-07-22 (adapter-build amendments; pre-data)

Published **before any scored run**, per §8 ("Config pins land as a dated v0.1.x amendment
before any scored run"). The metric core (§1-§4, §6, §7, §9) and the funnel, exclusions,
operators, and interpretation bands are **unchanged**. Every change below touches only §5
(detection-act mappings) and §8 (frozen parameters), and each is a pre-data correction made
to keep the published surfaces adjudicable and honest before numbers exist — which is the
whole defense against bias accusations.

1. **§5 LangGraph — "checkpoint rejections" removed.** No such API concept exists in
   langgraph 1.2.9 (confirmed absent from the persistence docs). Counted surfaces restated as
   interrupts (`langgraph.types.interrupt`, via the `__interrupt__` result key),
   validator/guardrail node outputs, and explicit error/review routing (`Command(goto=...)`).
2. **§5 CrewAI — "manager reassignment carrying an anomaly reason" → soft tier.** crewai
   1.15.5 emits no structured anomaly-reason event; hierarchical delegation is an ordinary
   tool call (`DelegateWorkTool`) whose reason is manager-LLM free text, not deterministically
   adjudicable. Also recorded: the docs' `LLMGuardrailFailedEvent` does not exist in 1.15.5;
   `LLMGuardrailCompletedEvent(success=False)` is the equivalent reject signal.
3. **§5 all frameworks — verdict-token protocol published verbatim** (`VERDICT: APPROVE` /
   `VERDICT: REJECT - <reason>`; case-insensitive first-match parse
   `VERDICT:\s*(APPROVE|REJECT)\s*(?:-\s*(.*))?`; no token = no hard-tier act), plus a
   per-framework per-act mapping table (act → mechanism), the rule that CrewAI
   guardrail-retry exhaustion is scored **escalate** (never `RUN_ERROR`) mirroring LangGraph's
   validator escalate-via-`interrupt()`, and the deterministic-guardrail **fairness rule**
   (pipeline guardrail/validator code implements only the published output contract; the
   semantic oracle lives only in the scorer).
4. **§8 temperature correction.** `gpt-5.6-terra` accepts only its default temperature
   (explicit `temperature=0` → HTTP 400 on the raw Chat Completions path; langchain-openai
   silently strips `temperature` for gpt-5* models — both verified live during the adapter
   build). No temperature parameter is transmitted by any adapter; every call runs at the
   model default, uniformly. The v0.1 "temperature 0" wording is corrected; fairness-by-
   uniformity is preserved because the knob does not exist on this model.
5. **§8 config pins filled** for all three frameworks (default + best-documented-guardrail),
   with exact pinned versions (langgraph 1.2.9 + langchain-openai 1.4.0; crewai 1.15.5;
   autogen-agentchat/-core/-ext 0.7.5) and doc links. AutoGen is pinned 0.7.5 with an honest
   maintenance-mode note; Microsoft `agent-framework` 1.12.0 is named the wave-2 candidate.
6. **§8 O4 downgrade model pinned** — `gpt-5.6-luna`, the same-generation next rung below the
   pipeline model, live-checked 2026-07-22 against OpenAI's models/pricing pages.

**Maintainer sign-off at the plan gate, dated 2026-07-22**, for the three decisions that
required it: (1) removing LangGraph "checkpoint rejections"; (2) moving CrewAI manager
reassignment to the soft tier; (3) pinning `autogen-agentchat==0.7.5` with the maintenance-mode
note and `agent-framework 1.12.0` as the wave-2 candidate. Full rationale, the temperature
evidence, and the O4 live-check record: `docs/decisions/2026-07-22-adapter-config-pins.md`.
