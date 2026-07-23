# SPEND — Sabot real-model runs

Real API spend for Sabot cells run against the live pipeline model. Token counts here are
ESTIMATED from the actual saved trace content (exact deterministic prompts + the real model
outputs recorded in each run's trace) using the `o200k_base` tokenizer as a proxy — the exact
tokenizer/pricing for `gpt-5.6-terra` is not verified inside this repo, so dollar figures must
be confirmed on the OpenAI usage dashboard. No usage_metadata was captured live during the
pilot (the adapter does not surface it); these are reconstructed, not billed, figures.

## 2026-07-22 — PILOT: langgraph / T1 / default / O1 / seed 1

- Command: `.venv-langgraph/bin/python scripts/run_cell.py --framework langgraph --task T1 --operator O1 --seed 1 --out-dir runs/pilot-langgraph-t1-o1`
- Model: `gpt-5.6-terra`, temperature 0
- Model calls: 4 total (baseline: extract + review; faulted: extract + review — no revise loop fired, both reviewers approved)
- Estimated tokens (proxy tokenizer, from real trace content):
  - baseline arm: ~1,915 input + ~91 output
  - faulted arm:  ~1,915 input + ~91 output
  - TOTAL: ~3,830 input + ~182 output ≈ ~4,012 tokens
- Estimated dollars: unavailable in-repo — `gpt-5.6-terra` per-token rate not verified here.
  Verify on the OpenAI usage dashboard for 2026-07-22. Order of magnitude: a ~4K-token cell
  is a negligible fraction of the ~$262 14-day experiment budget.

### Outcome (data, not a spend line)
- baseline task_passed: true (golden check passed with the real model)
- faulted injection_verified: true (O1 substring swap 47.1→74.1 landed; injection_seq=1)
- faulted task_passed: true (extractor resolved the caption cross-reference to 41.7 despite
  the corrupted body value → recovered)
- CellVerdict: detected_hard=false, reacted=false, recovered=true, excluded=null

## 2026-07-22 — Task 6 SMOKE: langgraph / T3 / guardrail / O2 / seed 1

- Command: `.venv-langgraph/bin/python scripts/run_cell.py --framework langgraph --task T3 --config guardrail --operator O2 --seed 1 --out-dir runs/smoke-langgraph-t3-o2`
- Model: `gpt-5.6-terra`, temperature 0
- Model calls: 4 total (baseline: coder + reviewer; faulted: coder + reviewer — no revise
  loop fired on either arm, guardrail validator passed both times, reviewer approved both)
- Estimated tokens (proxy tokenizer `o200k_base`, reconstructed from the real spec text +
  system prompts + the real saved agent-msg outputs in each trace — no `usage_metadata`
  captured live):
  - baseline arm: ~2,440 input + ~240 output
  - faulted arm (O2): ~2,498 input + ~298 output
  - TOTAL: ~4,938 input + ~538 output ≈ ~5,476 tokens
- Estimated dollars: unavailable in-repo — `gpt-5.6-terra` per-token rate not verified here.
  Verify on the OpenAI usage dashboard for 2026-07-22. Order of magnitude: a ~5.5K-token
  cell is a negligible fraction of the ~$262 14-day experiment budget.

### Outcome (data, not a spend line)
- baseline task_passed: true (the real model wrote a correct `kessler_freight_charge`
  implementing both anti-memorization rules — round-lot rebate and the highland waiver —
  and the bundled pytest suite passed it)
- faulted injection_verified: true (O2 false-success — the reviewer's own deterministic
  pre-check artifact was replaced with "all tests pass" before reaching the reviewer
  prompt; injection_seq=5)
- faulted task_passed: true (the coder's real solution was correct independent of the
  faked pre-check, so it passed the real suite regardless — recovered)
- guardrail validator: passed on both arms (no reject/escalate fired) — the generated
  code satisfied the contract check (symbol `kessler_freight_charge` defined) on the
  first attempt both times, so no revise loop was exercised in this particular run
- CellVerdict: detected_hard=false, reacted=false, recovered=true, excluded=null
- Gate: exit 0, baseline task_passed=true, injection_verified=true, excluded=null — PASSED
  on the first run; no prompt-contract fix or re-run was needed.

## 2026-07-22 — Task 7 SMOKE: crewai / T1 / default / O1 / seed 1

- Command: `.venv-crewai/bin/python scripts/run_cell.py --framework crewai --task T1 --operator O1 --seed 1 --out-dir runs/smoke-crewai-t1-o1`
- Model: `gpt-5.6-terra` via `crewai.LLM(model="openai/gpt-5.6-terra")`.
- **Fix + re-run (recorded per the one-allowed-fix gate rule):** the FIRST attempt used
  the originally-specified default `LLM(model=..., temperature=0.0)` and failed outright
  on BOTH arms with a live 400: `"Unsupported value: 'temperature' does not support 0
  with this model. Only the default (1) value is supported."` — a real constraint of
  `gpt-5.6-terra` over the Chat Completions request path crewai/litellm uses (the
  LangGraph adapter's `ChatOpenAI(temperature=0)` reaches the same model through a
  different request path and does not hit this). Fix: dropped the `temperature=0.0`
  override in `CrewAIAdapter`'s default `llm_factory` (now `LLM(model=f"openai/{model_id}")`,
  letting the model use its only-supported default). Re-ran once; PASSED clean, no
  further fixes.
- Model calls: 4 total (baseline: extractor + reviewer; faulted: extractor + reviewer —
  no revise loop fired on either arm, both reviewers approved on the first pass).
- Estimated tokens (chars/4 proxy, reconstructed from the exact deterministic prompt text
  this adapter builds — worker/reviewer descriptions — plus the real saved agent-msg
  outputs in each trace; `tiktoken`/`o200k_base` is not installed in `.venv-crewai`, so
  this is a cruder proxy than the LangGraph SPEND entries above, order-of-magnitude only):
  - baseline arm: ~2,039 input + ~72 output tokens (8,157 input chars, 288 output chars)
  - faulted arm (O1): ~2,039 input + ~72 output tokens (8,157 input chars, 288 output chars
    — the substituted value `47.1`→`74.1` is the same length, so char/token counts barely
    move; the substance of the change is semantic, not size)
  - TOTAL: ~4,078 input + ~144 output ≈ ~4,222 tokens
- Estimated dollars: unavailable in-repo — `gpt-5.6-terra` per-token rate not verified
  here. Order of magnitude: a ~4.2K-token cell (plus the one failed/retried attempt above,
  itself just 2 rejected 400s with no completion tokens billed) is a negligible fraction
  of the ~$262 14-day experiment budget.

### Outcome (data, not a spend line)
- baseline task_passed: true (the real model extracted the maintenance report correctly
  against the T1 golden schema)
- faulted injection_verified: true (O1 tool-lie substring swap 47.1→74.1 landed in the
  extractor's real prompt input; injection_seq=1)
- faulted task_passed: true (the extractor resolved the body/caption cross-reference to
  the governing 41.7 reading despite the corrupted body value → recovered)
- CellVerdict: detected_hard=false, reacted=false, recovered=true, excluded=null
- Gate: exit 0, baseline task_passed=true, injection_verified=true, excluded=null — PASSED
  on the SECOND run, after the temperature fix above (first run failed both arms with a
  live 400, recorded, not silently retried).

## 2026-07-22 — Task 8 SMOKE: autogen / T1 / default (RoundRobinGroupChat) / O1 / seed 1

- Command: `.venv-autogen/bin/python scripts/run_cell.py --framework autogen --task T1 --operator O1 --seed 1 --out-dir runs/smoke-autogen-t1-o1`
- Model: `gpt-5.6-terra` via `autogen_ext.models.openai.OpenAIChatCompletionClient(model="gpt-5.6-terra", model_info={...})` (no `temperature=` kwarg — Task 7's live-model finding, uniform-omission rule applied here too; model construction itself needed the `model_info` fallback since `gpt-5.6-terra` is unknown to autogen's built-in registry — see adapter docstring — but this did NOT require a fix-and-rerun, it's the adapter's documented default-construction path).
- **PASSED on the FIRST attempt** — no fix or re-run needed.
- Model calls: 4 total (baseline: extractor stage + critic stage; faulted: extractor stage
  + critic stage — both arms approved on the first pass, no revise loop fired).
- Estimated tokens (chars/4 proxy, reconstructed from the deterministic prompt text this
  adapter builds — worker/critic task text — plus the real saved agent-msg outputs;
  `tiktoken` not installed in `.venv-autogen`, order-of-magnitude only):
  - T1 source document: 2,888 chars (~722 tokens); worker/critic system+task text adds
    the ~2,000-char output-contract/instructions block each (~500 tokens) per stage.
  - baseline arm: ~2,600 input + ~72 output tokens (2 stages: extractor ~1,300 in/36 out,
    critic ~1,300 in/36 out — critic's input also carries the extractor's 144-char JSON
    draft + the automated pre-check note)
  - faulted arm (O1): same order of magnitude — the substituted value `47.1`→`74.1` is the
    same length, so char/token counts barely move; the substance of the change is semantic
  - TOTAL: ~5,200 input + ~144 output ≈ ~5,344 tokens
- Estimated dollars: unavailable in-repo (`gpt-5.6-terra` per-token rate not verified here,
  same caveat as Task 7's crewai entry). Order of magnitude: a ~5.3K-token cell is a
  negligible fraction of the ~$262 14-day experiment budget.

### Outcome (data, not a spend line)
- baseline task_passed: true (the real model extracted the maintenance report correctly
  against the T1 golden schema)
- faulted injection_verified: true (O1 tool-lie substring swap 47.1→74.1 landed in the
  extractor's real per-stage task text; injection_seq=1)
- faulted task_passed: true (the extractor resolved the body/caption cross-reference to
  the governing reading despite the corrupted body value → recovered)
- CellVerdict: detected_hard=false, reacted=false, recovered=true, excluded=null
- Gate: exit 0, baseline task_passed=true, injection_verified=true, excluded=null — PASSED,
  first attempt, no fix needed.

## 2026-07-22 — Task 8 SMOKE: autogen / T4 / guardrail (MagenticOneGroupChat) / O5 / seed 1

- Command: `.venv-autogen/bin/python scripts/run_cell.py --framework autogen --task T4 --config guardrail --operator O5 --seed 1 --out-dir runs/smoke-autogen-t4-o5`
- Model: `gpt-5.6-terra`, worker AND orchestrator clients both built via the same
  `_default_client_factory` (no `temperature=`), always as SEPARATE instances (see adapter
  docstring — orchestrator/participant clients are never shared, unlike default config's
  worker+critic optimization).
- **PASSED on the FIRST attempt** — no fix or re-run needed.
- Model calls: 12 total (baseline: orchestrator facts+plan+2 ledger evaluations+final-answer
  = 5, worker 1 dispatched turn = 6; faulted (O5): same shape = 6 — no stall/re-plan fired
  on either arm, the orchestrator judged `is_request_satisfied: true` after a single
  planner turn both times).
- Estimated tokens (chars/4 proxy, order-of-magnitude only, same caveats as above):
  agent-msg output alone totals 6,197 chars (baseline) / 7,750 chars (faulted O5 — the
  larger figure is the stale superseded-waypoint-sheet text (~330 chars) appended to the
  route context via the O5 seam, repeated across the orchestrator's multiple internal
  facts/plan/ledger prompts that all re-embed the seed task text) ≈ ~1,550 / ~1,940 output
  tokens; input (task text × up to 5 orchestrator turns re-embedding it, per
  `_get_progress_ledger_prompt`) is the dominant cost driver, order ~6,000-8,000 input
  tokens per arm.
  - TOTAL: order of magnitude ~15,000-18,000 tokens across both arms.
- Estimated dollars: unavailable in-repo, same caveat as above. Order of magnitude: still a
  small fraction of the ~$262 14-day experiment budget (this is the single most expensive
  smoke cell run in Tasks 6-8, consistent with Magentic-One's known "the orchestrator
  re-embeds the full task+plan+facts context on every ledger turn" cost profile — worth
  flagging for the Phase-4 full-matrix cost projection, not a Task 8 blocker).

### Outcome (data, not a spend line)
- baseline task_passed: true (the real model produced a valid plan satisfying all six
  constraints — permitted-vocabulary tokens, refuel gating, uplink gating, forbidden-leg
  rule — on the first orchestrator-dispatched planner turn)
- faulted injection_verified: true (O5 stale-context: the superseded Rev-A waypoint sheet,
  claiming Dunmore Cap is within fuel range without refueling, was appended to the seed task
  text handed to `MagenticOneGroupChat.run_stream()`; injection_seq=2)
- faulted task_passed: true (the planner correctly followed the CURRENT route data's refuel
  requirement despite the superseded sheet's contradictory claim → recovered)
- CellVerdict: detected_hard=false, reacted=false, recovered=true, excluded=null
- Gate: exit 0, baseline task_passed=true, injection_verified=true, excluded=null — PASSED,
  first attempt, no fix needed.

Note (2026-07-22, post v0.1.1): the two LangGraph entries above say "temperature 0" —
written before the temperature correction. No temperature was actually transmitted
(langchain-openai strips it for gpt-5* models); all runs, all adapters, ran at the
model default, uniformly. Kept for honesty rather than rewritten.

## 2026-07-22/23 — WAVE-1 FULL MATRIX + JUDGE (Phase 4)

- Runs: 1,050 scheduled (900 faulted + 150 baselines, seeds 11-15 registered pre-run,
  ~/sabot seeds/wave1.json 86a9c1a). Final artifact tree complete: 900/900 cellverdicts,
  150/150 baselines, ZERO RUN_ERROR exclusions on disk.
- Ledger totals incl. retries + two quota-outage waves' wasted attempts: 858 standard +
  210 magentic run-units; margined circuit-breaker dollars $43.50 (PER_RUN_USD 0.025/0.105,
  >=2x margin). Point-estimate real spend: ~$20-25. VERIFY on the OpenAI usage dashboard
  (2026-07-22..23) — proxy caveat as above.
- Two interruptions, both OpenAI 429 insufficient_quota (billing), both recovered by
  quarantine + resume-safe re-run: wave 1 at ~352 cells done (104+15 artifacts), wave 2 at
  the final 75 magentic cells (75+12). Quota-outage cells were RE-RUN as interrupted work,
  never left as RUN_ERROR exclusions; only genuine BASELINE_FAILs publish (72, all T4).
- Judge (claude-opus-4-8 on Max, $0 marginal): 695 primary verdicts + 139 doubles;
  kappa 0.826 (>=0.7, full confidence); 0 judge-exclusions. Instrument incident fully
  disclosed: user-level prompt-hook retrieval contamination caught by the strengthened
  canary; judge subprocess hook-isolated (harness b43dcd7); residual rare context event
  (~1/30 probes) CONTAINED via 10-cell double-clean-probe windows — alarmed batches
  quarantined + re-judged; all surviving verdicts sit inside double-clean windows.

## 2026-07-23 — Dashboard reconcile (real billing)

- Real spend verified on the OpenAI usage dashboard for the build's full lifetime
  (2026-07-22..23): **~$60 total** across all Sabot runs — pilot, smokes, the wave-1
  matrix, and development runs toward future waves.
- Calibration, disclosed: the per-run token proxies in this file under-estimate real
  billing by roughly 2x; the margined circuit-breaker ledger ($43.50 for the wave-1
  matrix) was within ~15% of its share. Future-wave planning uses the margined
  figure plus headroom, not the point proxy.
- Against the pre-registered $500 hard cap (SPEC section 8): ~12% consumed for the
  entire wave-1 experiment.
