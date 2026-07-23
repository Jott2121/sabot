# Wave-1 full-matrix cost projection (2026-07-22, pre-run)

Computed mechanically before launching the scored matrix (Phase 4 Task 8). STOP RULE:
a margined projection over $500 cuts seeds 5 -> 3 (via a new, disclosed registration
commit BEFORE any scored run) — cells are never cut first.

## Run counts (with baseline caching)

- Baselines: 3 frameworks x 2 configs x 5 tasks x 5 seeds = 150 (25 magentic)
- Faulted: 3 x 2 x 6 operators x 5 tasks x 5 seeds = 900 (150 magentic)
- Profiles: standard 875 runs, magentic (autogen guardrail / MagenticOneGroupChat) 175 runs

## Measured per-run token counts (SPEND.md, 2026-07-22 pilot + smokes; proxy tokenizers)

- standard: ~1,900-2,700 input + ~70-300 output tokens per arm
- magentic: ~7,000-9,000 input + ~1,750-2,000 output tokens per arm

## Published pricing (SPEC section 8, live-checked 2026-07-22)

gpt-5.6-terra: $2.50/M input, $15.00/M output. (O4 cells swap one agent to
gpt-5.6-luna at $1.00/$6.00 — cheaper; treated as terra here, conservative.)

## Point estimate

- standard: ~3,000 in + ~300 out with T2/T5 corpus margin => ~$0.012/run x 875 = ~$10.50
- magentic: ~8,000 in + ~2,000 out => ~$0.05/run x 175 = ~$8.75
- TOTAL point estimate: ~$19

## Margined projection (the driver's circuit-breaker constants, >=2x for revise loops + retries)

`spent_usd({"standard": 875, "magentic": 175})` = **$40.25**
(PER_RUN_USD = standard $0.025, magentic $0.105 — sabot/matrix.py, mutation-hardened)

## Verdict vs the $500 hard cap

UNDER at 5 seeds by >12x margin => **5 seeds stand; GO.**
The driver aborts automatically at $500 projected regardless (SystemExit "HARD CAP").

## Caveat (same as SPEND.md)

Proxy tokenizers + published pricing; the OpenAI usage dashboard is the billing truth
and is checked after the run.
