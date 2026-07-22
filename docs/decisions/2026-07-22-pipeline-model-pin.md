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

Correction (post-review): an earlier draft of this doc quoted invented tier
labels ("Mid-tier", "Mid-Tier & Compact") that do not appear on either page.
Re-fetched both pages verbatim below; the models page lists Sol/Terra/Luna
under one single umbrella heading, **"Frontier models"** — there is no
per-model tier label at all, only a one-line description per model. The
pricing page likewise lists every model (Sol, Terra, Luna, gpt-5.4-mini,
gpt-5.5, gpt-5.4, the `-pro` SKUs, etc.) under one single heading,
**"Flagship models"** — that heading is not a tier distinction either, it is
the page's label for its base (non-batch/flex/priority) rate table covering
every model. `gpt-5.4-mini` does not appear on the models page's current
"Frontier models" lineup at all (Sol/Terra/Luna only); it exists only as a
row in the pricing page's table.

| model | page's verbatim per-model description | input | cached input | output |
|---|---|---|---|---|
| `gpt-5.6-terra` | "GPT-5.6 model that balances intelligence and cost" (models page, under "Frontier models") | $2.50 | $0.25 | $15.00 |
| `gpt-5.6-luna` | "GPT-5.6 model optimized for cost-sensitive workloads" (models page, under "Frontier models") | $1.00 | $0.10 | $6.00 |
| `gpt-5.4-mini` | not present on the models page's current lineup; appears only as a pricing-table row under the pricing page's single "Flagship models" heading (previous-generation "mini" SKU) | $0.75 | $0.075 | $4.50 |

For reference, `gpt-5.6-sol` — the third model under the same "Frontier
models" heading — is described as "Frontier model for complex professional
work" and priced at $5.00/$30.00. Flagship-priced models `gpt-5.5` ($5.00/
$30.00), `gpt-5.4` ($2.50/$15.00), and the `-pro` SKUs ($30.00/$180.00) were
read and rejected outright: nothing in the brief calls for flagship
reasoning-grade capability, and several of these cost 2-12x the candidates
above for no stated agent-stack advantage.

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

- **Capability/credibility half:** neither page assigns formal tiers, so this
  reads from the real per-model descriptions and the price ladder instead.
  Among the three current-generation "Frontier models," `gpt-5.6-terra` sits
  in the middle of the price ladder ($2.50/$15.00 — below Sol's $5.00/$30.00
  "frontier model for complex professional work," above Luna's $1.00/$6.00),
  and its own description is explicitly the balanced general-purpose one,
  "GPT-5.6 model that balances intelligence and cost" — not a capability
  trade-off in either direction. Luna's description commits the opposite way
  ("optimized for cost-sensitive workloads" — a budget trim, current
  generation but explicitly cost-first) and `gpt-5.4-mini` is a previous-
  generation "mini" SKU that isn't even part of the current frontier lineup.
  Pinning either invites the "you handicapped the pipeline" objection this
  rule exists to pre-empt; `gpt-5.6-terra`'s own stated description and its
  mid-ladder price do not.
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
