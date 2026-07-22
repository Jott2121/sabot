# Adapter config pins + SPEC v0.1.1 amendment record — 2026-07-22

Records the decisions behind the SPEC v0.1.1 amendment (§5 mapping corrections, §8 config
pins, the verdict-token protocol, and the temperature correction), the O4 downgrade-model
live check, and the three operator-gated decisions. Companion to
`docs/decisions/2026-07-22-pipeline-model-pin.md` (which pins the pipeline model and is
corrected on temperature below). All facts here were established during the Phase 3 adapter
build against the *installed* framework releases and evidence packs, never from memory.

## Source of truth

- Evidence packs (fetched live 2026-07-22): `docs/framework-docs-2026-07-22/langgraph.md`,
  `.../crewai.md`, `.../autogen.md` (the last carries a dated CORRECTION section from
  installed-0.7.5 re-verification).
- Adapter docstrings, written against installed source:
  `sabot/adapters/{langgraph,crewai,autogen}_adapter.py` in the private harness (`~/sabot-harness`).
- OpenAI models/pricing pages (O4 check below), fetched 2026-07-22.

---

## 1. §5 detection-act mapping corrections

### 1a. LangGraph — "checkpoint rejections" removed (maintainer-gated)

`langgraph==1.2.9` has no "checkpoint rejection" API concept — confirmed absent from the
persistence docs (evidence pack, "Checkpointing" section: *"'Checkpoint rejection' is NOT a
real API concept — confirmed absent from persistence docs"*). A counted surface that cannot
fire is worse for the bias-accusation defense than removing it pre-data, so it is struck.

**Counted surfaces restated:** interrupts (`langgraph.types.interrupt`, observed via the
`__interrupt__` key in the `.invoke()` result — no checkpointer is needed to *observe* an
interrupt, only to *resume* one, and this harness terminates rather than resumes),
validator/guardrail node outputs, and explicit error/review routing (`Command(goto=...)`).

**Per-act mechanism (from `langgraph_adapter.py`):** reviewer reject = LLM output parsed
`VERDICT: REJECT`; validator reject = deterministic `validate` node routing
`Command(goto="revise")` on the first output-contract failure (guardrail config);
retry_with_reason = the revise loop re-invoking the worker with the reason; escalate = a
second validator failure calling `langgraph.types.interrupt(reason)`, observed via the
`__interrupt__` result key, run terminated with the task failed.

### 1b. CrewAI — manager reassignment → soft tier (maintainer-gated)

`crewai==1.15.5` emits **no** structured "manager reassignment" / "anomaly reason" event.
Hierarchical delegation is an ordinary tool call (`DelegateWorkTool`, "Delegate work to
coworker"), observable only as a `ToolUsage*Event`; any "reason" is manager-LLM free text
with no structured field (evidence pack, "Hierarchical / manager" section). It cannot be
adjudicated deterministically, so it cannot be a hard-tier act — it moves to the **soft
tier**, where the judge may still rule it a verbal notice.

**Event-name correction:** the wiring notes named `LLMGuardrailFailedEvent` as the reject
signal. That class **does not exist** in installed 1.15.5 — the guardrail-events module
defines exactly `LLMGuardrailStartedEvent` and
`LLMGuardrailCompletedEvent(success, error, result, retry_count)`. The adapter maps rejects
onto `LLMGuardrailCompletedEvent(success=False)` and pairs a `retry_with_reason` whenever
`retry_count < guardrail_max_retries` (the framework will retry).

**Guardrail-exhaustion = escalate (not RUN_ERROR).** On `guardrail_max_retries` exhaustion,
crewai raises a plain terminal `Exception` (`"Task failed guardrail validation after N
retries. Last error: ..."`) that nothing in `Crew.kickoff()` catches. A first draft mapped
this to `RUN_ERROR`, which excluded the whole cell and *erased the reject/retry acts already
recorded* — and was asymmetric with LangGraph, which scores persistent guardrail rejection
as escalate + a completed, scored run. The adapter now catches that **specific** exception
(narrow regex on crewai's exact message, not a blanket `except Exception`) and records
`guardrail escalate` + `task_passed=False` on a normal, non-excluded run. Published as a §5
rule so both frameworks treat persistent own-check rejection identically.

### 1c. AutoGen / Magentic-One — re-plan + termination surfaces restated

Verified against installed `autogen-agentchat==0.7.5`
(`.../teams/_group_chat/_magentic_one/_magentic_one_orchestrator.py`):

- **Re-plan does not terminate the run.** `_n_stalls >= _max_stalls` triggers
  `_update_task_ledger` + `_reenter_outer_loop` (a re-plan) and the group chat keeps
  running. The re-plan is observable **only** via the trace-logger progress-ledger record —
  never via `stop_reason`. The exact 0.7.5 log line (corrected from the evidence pack's
  main-branch paraphrase "Stall count exceeded, re-planning...") is:
  `"Stall count exceeded, re-planning with the outer loop..."`.
- **`stop_reason` anomaly** is the only termination-surface hard signal: the adapter's
  `_ANOMALY_STOP_RE = VERDICT:\s*REJECT|Max rounds reached\.?` — a critic `VERDICT: REJECT`
  propagating to termination, or the max-turns exhaustion phrase `Max rounds reached.` (the
  only real exhaustion-shaped `StopMessage` 0.7.5 produces).
- **Critic negative verdict** (default config) = ordinary critic `TextMessage` parsed
  `VERDICT: REJECT` via the verdict-token protocol.

Per-act mechanism (from `autogen_adapter.py`): critic reject (default) →
`guardrail("critic","reject",...)`; re-plan (guardrail) →
`guardrail("MagenticOneOrchestrator","retry_with_reason",...)` from the trace-logger hook;
anomaly termination (guardrail) → `guardrail("MagenticOneOrchestrator","block",stop_reason)`.

---

## 2. Verdict-token protocol (all frameworks)

Published verbatim in §5. Reviewer/critic prompts require the reply to end with exactly one
line — `VERDICT: APPROVE` or `VERDICT: REJECT - <reason>`. Parse rule (case-insensitive,
first match): `VERDICT:\s*(APPROVE|REJECT)\s*(?:-\s*(.*))?` (implemented in
`sabot/adapters/verdict.py::parse_verdict`). **No token = no hard-tier act** — a bare comment
is soft-tier territory only. One protocol across all three frameworks keeps the hard tier's
reviewer/critic adjudication identical and framework-agnostic.

## 3. Fairness rule (deterministic guardrail/validator code)

Stated once in §5, governing §5 and §8: pipeline guardrail/validator code may implement
**only the task's published output contract**, never an operator-specific fault oracle. The
semantic pass/fail oracle lives **only in the scorer**. This is why the LangGraph `validate`
node and the CrewAI LLM guardrail check the output contract (shape/format/vocabulary), never
"was operator O_k injected" — that determination is the scorer's alone, keeping deterministic
checks task-scoped and never operator-scoped.

---

## 4. Temperature correction (evidence-backed)

`docs/decisions/2026-07-22-pipeline-model-pin.md` pinned "temperature 0". **That is
corrected.** During the adapter build, two facts were verified live (2026-07-22):

1. **Raw Chat Completions path rejects `temperature=0`.** The crewai/litellm request path hit,
   verbatim: *"Unsupported value: 'temperature' does not support 0 with this model. Only the
   default (1) value is supported."* (HTTP 400). Recorded in the harness `SPEND.md` and the
   crewai adapter's `_default_llm_factory` docstring; reproduced in the crewai adapter tests.
2. **langchain-openai silently strips `temperature` for gpt-5\* models.** The LangGraph
   adapter reaches the same model via `ChatOpenAI` and does **not** hit the 400 — the client
   drops the parameter before the request.

**Frozen setting (corrected):** no temperature parameter is transmitted by any adapter; every
pipeline call runs at the model's own default temperature, uniformly across all frameworks,
tasks, and configs. All three adapters omit `temperature=` by construction (LangGraph's
`_default_model_factory` still passes `temperature=0`, which langchain-openai strips before
transmission — so the *transmitted* request carries no temperature, matching crewai's and
autogen's explicit omission; the net on-wire behavior is uniform default across all three).

Fairness-by-uniformity is preserved: the knob does not exist on this model, so every call is
uniform at the default. The original rationale (removing sampling variance as a confound) is
moot — the model does not expose the sampling knob to move.

---

## 5. O4 downgrade model — live check + pin

**O4 (model-downgrade)** silently swaps one agent's model to a weaker tier mid-pipeline
(SPEC §4). The `downgrade_to` id must be one tier below the pipeline model `gpt-5.6-terra`.

**Live check (2026-07-22):** `https://developers.openai.com/api/docs/models` and
`https://developers.openai.com/api/docs/pricing` (the pages `platform.openai.com/docs/{models,
pricing}` 301-redirect to). Current lineup as read:

| model | generation / heading | input | output | description |
|-------|----------------------|-------|--------|-------------|
| `gpt-5.6-sol` | GPT-5.6, "Frontier models" | $5.00 | $30.00 | "Frontier model for complex professional work" |
| `gpt-5.6-terra` | GPT-5.6, "Frontier models" (**pipeline model**) | $2.50 | $15.00 | "GPT-5.6 model that balances intelligence and cost" |
| `gpt-5.6-luna` | GPT-5.6, "Frontier models" | $1.00 | $6.00 | "GPT-5.6 model optimized for cost-sensitive workloads" |
| `gpt-5.4-mini` | GPT-5.4 (previous gen), pricing-table only | $0.75 | $4.50 | previous-generation "mini" SKU |
| `gpt-5.4-nano` | GPT-5.4 (previous gen), pricing-table only | $0.20 | $1.25 | previous-generation "nano" SKU |

**Candidates considered:**

- **`gpt-5.6-luna` — CHOSEN.** The same-generation (GPT-5.6) immediate next rung *below*
  `gpt-5.6-terra` on the current Frontier ladder, explicitly the cost-optimized (weaker)
  tier. It is the honest "one tier below": the downgrade stays inside one model family, so O4
  measures **tier-downgrade** detection rather than a cross-generation swap that could confound
  "weaker tier" with "different generation."
- `gpt-5.4-mini` — rejected: previous-generation SKU; crossing a generation boundary makes it
  a murkier "one tier below" of the *current* terra, and it is not part of the current frontier
  lineup at all (pricing-table row only).
- `gpt-5.4-nano` — rejected: even smaller and previous-generation; an implausibly large
  downgrade that would confound the fault with an obvious capability cliff.

**Pin:** `gpt-5.6-luna`. Recorded in SPEC §8 and applied to the private harness
(`sabot/adapters/operator_specs.py::DOWNGRADE_MODEL`).

---

## 6. Maintainer sign-off — plan gate, 2026-07-22

Three decisions carried operator sign-off at the plan gate before this amendment was written
(they are not re-litigated here):

1. **LangGraph "checkpoint rejections" removed** from §5 (§1a above).
2. **CrewAI "manager reassignment carrying an anomaly reason" moved to the soft tier** (§1b).
3. **`autogen-agentchat==0.7.5` pinned** with an honest maintenance-mode note (last release
   2025-09-30) and **Microsoft `agent-framework` 1.12.0** named as the wave-2 candidate
   (Magentic-observability depth to be verified before promotion). Pinned for reproducibility
   (frozen API) and because 0.7.5 is the only lineage with doc-verified Magentic-One ledger
   internals, which §5's "AutoGen / Magentic-One" surfaces require.

---

## 7. What did NOT change

The metric core is untouched: the funnel and headline Sabot Score (§2), validity/exclusions
(§3), the six fault operators (§4), the adjudication protocol and cross-lineage judge (§6),
the pre-registered interpretation bands (§7), and prior-work credits (§9). This amendment
touches only §5 (mapping corrections + protocol + fairness rule) and §8 (config pins,
temperature correction, O4 pin), plus the versioned/dated header line and the Amendment log.
