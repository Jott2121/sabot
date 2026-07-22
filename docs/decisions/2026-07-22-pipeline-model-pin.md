# Pipeline model pin — 2026-07-22

Fills SPEC.md §8 "Pipeline model: RECORDED AT FREEZE" and the companion
Temperature line. This is the one fixed OpenAI model (and temperature) used by
every agent, in every framework, in every run of the sprint matrix
(fairness-by-uniformity, §6).

## Source

Fetched live (no memory used): `https://platform.openai.com/docs/pricing` and
`https://platform.openai.com/docs/models` — both 301-redirect to
`https://developers.openai.com/api/docs/pricing` and
`https://developers.openai.com/api/docs/models` respectively, which is the
content actually recorded below. Fetched 2026-07-22.

## Selection rule

The mid-tier general model most plausibly used in production agent stacks
today — capable enough that a detection failure isn't dismissed as "you used
a toy model," cheap enough that the full run matrix fits inside the sprint's
$500 cap.

## Candidates (prices exactly as the pricing page states them, per 1M tokens)

| model | page-stated tier | input | cached input | output |
|---|---|---|---|---|
| `gpt-5.6-terra` | "Mid-tier" (models page: "Balances intelligence with cost-effectiveness") | $2.50 | $0.25 | $15.00 |
| `gpt-5.6-luna` | "Cost-optimized" (models page: "Optimized for cost-sensitive workloads") | $1.00 | $0.10 | $6.00 |
| `gpt-5.4-mini` | "Mid-Tier & Compact" (pricing page), branded "mini" (models page lists it only as a compact/legacy-generation SKU) | $0.75 | $0.075 | $4.50 |

(Flagship-tier models — `gpt-5.6-sol` $5.00/$30.00, `gpt-5.5` $5.00/$30.00,
`gpt-5.4` $2.50/$15.00, the `-pro` SKUs at $30.00/$180.00 — were read and
rejected outright: nothing in the brief calls for flagship reasoning-grade
capability, and several of these cost 2-12x the mid-tier candidates above for
no stated agent-stack advantage.)

## Cost arithmetic

Working assumptions (stated per the brief, since no framework adapters are
built yet to measure this directly):

- **Runs:** 1,050 total (SPEC §8: 3 frameworks x 2 configs x 6 operators x 5
  tasks x 5 seeds = 900 fault runs, + 3 x 2 x 5 x 5 = 150 no-fault baselines).
- **~15 model calls/run, ~40,000 total tokens/run** (working estimate per the
  task brief, pending real measurement once adapters exist).
- **Input/output split:** assumed 70% input / 30% output per run (28,000 in /
  12,000 out). Multi-agent pipelines accumulate transcript + tool-output
  context across calls, which skews token count toward input; this is a
  stated assumption, not a measured one, and should be revisited once real
  adapter traces exist.
- No prompt-caching credit taken (conservative — treats every token as a
  fresh, uncached charge, even though repeated system/task context would
  likely earn the cached-input rate in practice).

Per-run cost = (28,000 / 1,000,000 x input price) + (12,000 / 1,000,000 x
output price).

| model | cost/run | x 1,050 runs | vs. $500 cap |
|---|---|---|---|
| `gpt-5.6-terra` | $0.07 + $0.18 = **$0.25** | **$262.50** | fits, ~47% headroom |
| `gpt-5.6-luna` | $0.028 + $0.072 = $0.10 | $105.00 | fits, ~79% headroom |
| `gpt-5.4-mini` | $0.021 + $0.054 = $0.075 | $78.75 | fits, ~84% headroom |

All three candidates clear the cost half of the rule comfortably. The choice
is decided by the capability/credibility half.

## Choice: `gpt-5.6-terra`

**Why it satisfies both halves of the selection rule:**

- **Capability/credibility half:** `gpt-5.6-terra` is the only candidate the
  models page itself labels **"Mid-tier"** as a first-class tier, current
  generation (5.6, not the superseded 5.4 line), described as balancing
  intelligence with cost — i.e., the general-purpose model OpenAI's own docs
  position for production use, not a mini/nano/cost-optimized trim. Pinning a
  model explicitly branded "mini" (`gpt-5.4-mini`) or "cost-optimized"
  (`gpt-5.6-luna`) invites the "you handicapped the pipeline" objection this
  rule exists to pre-empt; `gpt-5.6-terra` does not.
- **Cost half:** $262.50 for the full ~1,050-run matrix, well inside the $500
  cap, leaving roughly $237 of headroom for judge-side overhead (though the
  cross-lineage judge itself is $0 marginal on the Claude Max plan, §6),
  harness/API retries, and any upward revision of the 40k-token/run estimate
  once real adapter traces replace this working assumption.

No candidate busts the cap, so this is a capability-driven choice, not a
forced cheapest-option pick — the honest outcome, since the rule's two halves
did not conflict here.

## Temperature: 0

Pinned alongside the model id, uniform across every pipeline-model call in
every framework, task, and config, for the same fairness-by-uniformity reason
(SPEC §6, §8). Temperature 0 removes sampling variance as a confound between
frameworks — any difference in fault-detection outcome is attributable to the
framework/config/operator under test, not to run-to-run sampling noise in the
underlying model's outputs. The pre-registered seeds (§8) already carry the
per-run reproducibility requirement; temperature 0 does the same job for the
model's own token sampling.
