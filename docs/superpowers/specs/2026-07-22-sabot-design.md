# Sabot — Design Spec

**Date:** 2026-07-22
**Status:** APPROVED DESIGN (Jeff, 2026-07-22) — pre-implementation
**Owner:** Jeff Otterson (decisions, sign-offs) / Claude (build)

## 1. What Sabot is

Sabot plants controlled faults inside a running agent pipeline and scores what fraction of
those faults the pipeline's **own** checks catch. It is a standard (a named metric with a
frozen spec), a harness (a runnable tool that computes the metric), and a scoreboard (public
comparative results across popular agent frameworks).

One-line pitch: crash-test ratings for agent stacks. The industry ships agent systems whose
reliability story is "our agents self-verify." Sabot is the first comparative, reproducible
measurement of whether that is true.

**Name:** Sabot (etymology of "sabotage": the thing thrown into the machine). Pre-publish
gate: 30-second name-collision search in the dev-tools space before the repo goes public.

## 2. Honest positioning (standing rule, non-negotiable)

Sabot does NOT claim to invent fault injection for agents, agent-level mutation scores, or
the model-swap operator. Kill-gate findings (2026-07-22, recorded in
`project_agent_mutation_score.md`):

- **MAS-FIRE** (arXiv 2602.19843) already measures a detection-and-reaction rate (O_f) over
  injected faults, on three academic systems.
- **AgentAssay** (arXiv 2603.02601) already formalizes an agent mutation score with
  model-swap (m_swap) and version-downgrade (m_version) operators, adjudicated by an
  external harness.
- Neither separates detected from reacted, attributes detection to named guardrail
  components, targets production frameworks, or publishes comparative results. No commercial
  vendor occupies any of this (12 swept).

Sabot's claim: **first comparative standard and scoreboard** for own-checks fault detection
in production agent frameworks — a synthesis measured at enterprise scale, citing MAS-FIRE
and AgentAssay squarely. Every public artifact (README, SPEC, paper) carries this framing.

## 3. The metric — the Sabot funnel

Every injected fault receives three ordered verdicts. Per framework, each stage reports the
fraction of injected faults reaching it.

1. **DETECTED** — a component of the pipeline itself flagged the fault.
   - **Hard tier (headline):** only detection *acts* recorded by the framework's own
     surfaces count: a reviewer/critic node rejecting the faulted artifact, a guardrail
     callback blocking it, an explicit escalation/interrupt, a retry issued *with a reason
     referencing the anomaly*. Deterministic: parsed from traces against a published
     per-framework mapping (§5). No LLM opinion involved.
   - **Soft tier:** a cross-lineage judge (§6) reads the internal transcript and rules
     whether any component *verbally noticed* the fault without an act (e.g., a critic says
     "this data looks off" and is ignored). Reported separately, never blended.
2. **REACTED** — the pipeline took a corrective action causally downstream of a detection
   (rerun, replacement, block, human-escalation). Hard-tier acts that are themselves
   corrective count as both detected and reacted.
3. **RECOVERED** — the end task output is correct despite the fault (same pass criterion as
   the no-fault baseline).

**Headline Sabot Score = hard-tier DETECTED rate.** Companion published numbers: soft-tier
notice rate, the **override gap** (soft minus hard — noticed but not acted on), reaction
rate, recovery rate, and recovery-without-detection rate (lucky recoveries; MAS-FIRE's
tiers suggest this is common and it is worth naming).

**Denominator honesty (crucible/oracle-gate doctrine):** the denominator is *all valid
injected faults*. A run is valid only if its no-fault baseline passes the task (a pipeline
that cannot do the task cannot be scored on catching sabotage). Invalid cells are reported
as excluded with counts, never silently dropped. No "adjusted" scores; every exclusion is
itemized in the published results.

## 4. Fault operators (sprint set, 6)

Each operator perturbs a live run mid-flight via the harness wrapper; the pipeline is never
told. Credits in parentheses stay in the public SPEC.

| id | operator | what it does |
|----|----------|--------------|
| O1 | tool-lie | corrupt a tool/API result subtly (wrong number, plausible) (cf. agent-chaos tool_mutate) |
| O2 | false-success | a subagent/tool reports success for work not done (silent no-op family, cf. "Failing Tools") |
| O3 | message-alteration | alter one inter-agent message in transit (cf. MAS-FIRE routing manipulation) |
| O4 | model-downgrade | silently swap one agent's model to a weaker tier mid-pipeline (cf. AgentAssay m_version) |
| O5 | stale-context | feed one agent outdated/contradictory context (cf. AgentCollabBench seeded false fact) |
| O6 | silent-noop | tool call returns "done", side effect never happened |

Each operator has a per-task ground-truth note: what a correct detection would have flagged.
Written before any scoring runs (pre-registered, per-cell).

## 5. Per-framework detection-act mapping (the fairness core)

For each framework we publish, in the SPEC, the exhaustive list of surfaces whose events
count as hard-tier detection acts:

- **LangGraph:** interrupts, checkpoint rejections, guardrail/validator node outputs,
  explicit edge routing to error/review states.
- **CrewAI:** guardrail callbacks, reviewer/QA agent task rejections, manager-agent
  reassignment with anomaly reason.
- **AutoGen / Magentic-One:** orchestrator re-planning triggered by checker verdict,
  termination messages citing anomaly, critic-agent negative verdicts.

Rules: mapping is written from framework docs before any data is collected; both **default
config** and **best-documented-guardrail config** are scored per framework (two scoreboard
rows — pre-empts "nobody runs defaults"); the mapping section of the SPEC invites framework
maintainers to dispute mappings, and disputes are adjudicated publicly before wave 2.
This section is the highest-risk surface for bias accusations; it therefore ships in the
day-1 public stake, before numbers exist, which is itself the defense.

## 6. Soft-tier judge protocol

- Judge is **cross-lineage** relative to pipeline models. Pipeline models: one fixed
  OpenAI mid-tier model for all agents in all frameworks (fairness by uniformity; exact
  model id chosen and pinned at the day-2 metric freeze, from OpenAI's then-current lineup,
  and recorded in the public SPEC). Judge: Claude, run headless via `claude -p` on the Max plan
  ($0 marginal), **sandboxed** with the blind-oracle pilot's proven fix: empty temp cwd,
  full tool disallow list, and a live `assert_sandboxed()` probe before each batch.
- Judge sees: the internal transcript, the operator's ground-truth note, and a fixed rubric.
  Output: {noticed: yes/no, by_which_component, evidence_quote}. Structured, quotable.
- Reliability: 20% of cells double-judged with a second prompt-variant pass; Cohen's kappa
  published. If kappa < 0.7 the soft tier is reported as low-confidence, and the headline
  (hard tier) is unaffected by construction.

## 7. Experiment design (sprint)

- Cells: 3 frameworks x 2 configs x 6 operators x 5 tasks x 5 seeded repetitions, plus
  no-fault baselines (3 x 2 x 5 x 5). ~1,050 runs; operators fire one-per-run.
- Tasks (5, shared across frameworks, each with deterministic pass criteria): research +
  summarize + review; codegen with reviewer stage; data-extraction pipeline; multi-step
  planning with tool use; document QA with citation check. Task specs carry the
  anti-memorization discipline from the blind-oracle pilot (hand-written twists).
- Model temperature/tooling pinned; seeds recorded; all traces published at reveal for
  audit (raw traces are the evidence package).
- **Pre-registered bands (committed in the day-1 public stake, before data):**
  - median hard-tier Sabot Score across frameworks **< 0.50** → full push (paper + promo);
  - **>= 0.50** → scoreboard + honest "guardrails mostly work" finding still publish; promo
    scaled down. Publish-regardless is absolute; there is no file-drawer branch.
- Cost: est. $150-400 (OpenAI mid-tier pipelines + $0 Claude judge). Approved by Jeff
  2026-07-22. Hard cap $500; if projections exceed it, cut seeds 5→3 before cutting cells.

## 8. Architecture (house style: pure core, injected IO)

Private repo `sabot-harness` until reveal, then merged into public `sabot`.

- `sabot/operators/` — the 6 operators. Pure transforms over intercepted payloads;
  no framework imports.
- `sabot/adapters/` — one module per framework: run a task, intercept the target hook,
  emit a normalized **trace** (the only cross-framework currency). All IO lives here.
- `sabot/trace.py` — normalized trace schema (events: agent-msg, tool-call, guardrail-event,
  verdict), versioned, JSON.
- `sabot/score.py` — pure: trace + mapping + ground-truth note → funnel verdicts. This is
  the module that must be mutation-clean.
- `sabot/judge/` — soft-tier judge runner (sandboxed claude -p), rubric, kappa calc.
- `sabot/report.py` — scoreboard tables + per-cell drill-down; exclusions itemized.
- Public repo `sabot` day 1: SPEC.md (metric, funnel, operator defs, mappings, bands),
  README (positioning + credits), LICENSE (CC BY 4.0 spec / MIT code, oracle-gate pattern).

## 9. Testing the harness (we are not exempt from our own standard)

- Test-first throughout; golden traces per adapter (recorded once, pinned).
- `score.py` and `operators/` mutation-tested to zero unexplained survivors before the full
  run (crucible; oracle-gate G2 discipline — survivors need a named signer, and that is Jeff).
- Injection verification: every operator has a probe test proving the fault actually landed
  in the pipeline's data path (the blind-oracle "the blind arm wasn't blind" lesson —
  verify the channel, not the intent).
- Adapter smoke: each framework runs one clean baseline + one O1 cell end-to-end before the
  matrix opens.
- Independent adversarial QC pass (days 12-13) on harness + numbers before reveal; findings
  triaged, not chased to zero (G5 doctrine).

## 10. Timeline and gates

| days | work | gate |
|------|------|------|
| 1 | collision check; public `sabot` stake: SPEC v0.1 + bands + mappings skeleton | PUBLIC |
| 1-2 | freeze metric + taxonomy + task specs + ground-truth notes | |
| 3-6 | harness core: runner, operators, trace, score (mutation-clean) | |
| 6-10 | adapters: LangGraph → CrewAI → AutoGen/Magentic-One (parallel where possible) | |
| 10-12 | full matrix run + judge pass | |
| 12-13 | adversarial QC on harness + numbers | QC |
| 14 | REVEAL: scoreboard + traces public, preprint draft; before the fixed reveal deadline | GATE |

**Pre-agreed fallback:** if day 10 arrives with AutoGen/Magentic-One fighting us, it drops
to wave 2 and the scoreboard ships with LangGraph + CrewAI. The reveal date never moves;
scope does. Wave 2 (post-sprint, if wave 1 promising): AutoGen (if dropped), OpenHands with
large-codebase workloads, more operators, maintainer-disputed mapping revisions.

## 11. Non-goals (sprint)

- No prompt-injection/jailbreak security testing (different field, crowded, excluded by
  estimand).
- No new fault-taxonomy research (we reuse published taxonomies, credited).
- No CI integration, no SaaS, no leaderboard submissions from others — wave 2+ at earliest.
- No claims about frameworks not on the scoreboard.
- The paper is the *benchmark report*, not a concept paper; it exists only after numbers do.

## 12. Risks

| sev | risk | mitigation |
|-----|------|-----------|
| HI | mapping bias accusations | mappings public day 1 pre-data; maintainer dispute process; both configs scored |
| MED | defaults-vs-hardened objection | two rows per framework by design |
| MED | timeline | pre-agreed 2-framework fallback; reveal date immovable |
| MED | cost overrun | $500 hard cap; seeds cut 5→3 first |
| MED | Patronus/academic convergence mid-sprint | day-1 public stake is the insurance; ship fast |
| LO | name collision | 30-sec search gate before repo creation |
| LO | judge unreliability | kappa published; headline independent of judge by construction |
