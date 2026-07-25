# Sabot: Do Multi-Agent Frameworks' Own Checks Detect Injected Faults?

**A pre-registered comparative scoreboard — wave 1**

Jeff Otterson
`github.com/Jott2121/sabot` — specification and results CC BY 4.0, harness Apache-2.0

*Version 1 — 2026-07-23. The complete evidence package — frozen specification
(v0.1.3, tagged), pre-registered seeds, harness, raw traces, and the
pre-publication QC ledger — is public at `github.com/Jott2121/sabot`.*

> **Post-publication statistical supplement (dated note, 2026-07-25).** A
> statistical supplement published after this paper's release
> (`harness/runs/wave2/UNCERTAINTY.md`) adds exact replicate-cluster bootstrap
> intervals to this paper's point estimates: the 16.7% median hard-tier
> detection carries a 95% CI of [15.6, 17.8]. Two clarifications from that work
> apply here: (1) the "seeds" (11-15) were never passed to the model or any RNG
> — they are replicate labels on five stochastic repetitions; (2) framework
> rows whose intervals overlap are not ranked by this data. The supplement and
> the prospective rule adoptions from wave-2 QC ship as SPEC v0.2.1 (see the
> SPEC Amendment log); this paper's text and numbers are unchanged. One
> instrument defect disclosed 2026-07-25 also touches this paper: the T3
> adapters serve the task file's ground-truth section to the pipeline, so
> T3's reviewer had the fault catalog in view — and still detected almost
> nothing on this paper's surfaces, which restates rather than weakens the
> finding. Details and a sensitivity bound: the QC ledger addendum.

---

## Abstract

Production multi-agent frameworks ship reviewer stages, guardrail callbacks, and
orchestration ledgers that are widely presumed to catch faults arising inside a
pipeline. We measure whether they do. Sabot injects a single controlled fault into a
live multi-agent run — a subtly corrupted tool result, a falsified success report, an
altered inter-agent message, a silent model downgrade, stale context, or a silent
no-op — and scores whether the pipeline's *own* components detect it, with no
external instrumentation in the detection path. Across 900 injected faults spanning
three production frameworks (LangGraph, CrewAI, AutoGen/Magentic-One), two
configurations each (default and best-documented-guardrail), five tasks, six fault
operators, and five pre-registered seeds, the median hard-tier detection rate — a
detection *act* by the pipeline's own surfaces, adjudicated deterministically against
per-framework mappings published before any data existed — is **16.7%**. No
framework's pooled detection exceeds 19.8%. Guardrail configurations do not
materially outperform defaults. The dominant outcome everywhere is
**recovery-without-detection** (51–61% of valid faults in every scoreboard row): the
task output is correct despite the fault while nothing in the pipeline ever flags it.
Trace analysis shows the underlying mechanism is that the pipeline model frequently
notices the anomaly and routes around it without emitting any detection act. All
seeds, interpretation bands, and detection-act mappings were published before
measurement; raw traces, the scoring harness, and an adversarial pre-publication QC
ledger are released as an evidence package. Sabot is a synthesis and comparative
measurement at production-framework scale of ideas introduced by MAS-FIRE
(own-mechanism fault detection) and AgentAssay (agent-level mutation scoring,
model-swap operators); it claims invention of neither.

## 1. Introduction

Multi-agent pipelines increasingly gate real work — code review, data extraction,
planning, document QA — behind their own internal quality machinery: reviewer agents,
deterministic guardrail callbacks, escalation interrupts, orchestration progress
ledgers. That machinery is the basis for a widespread operational assumption: if
something goes wrong mid-pipeline, some check will catch it.

Sabot tests the assumption directly. It plants one controlled fault per run into a
live pipeline execution, without the pipeline being told, and asks a narrow question:
**did anything the pipeline itself owns act on the fault?** Not whether an external
monitor could have seen it, not whether the final answer happened to come out right —
whether the system's own checks fired.

The measurement discipline is the contribution:

1. **A hard/soft detection firewall.** The headline number counts only detection
   *acts* recorded by the framework's own surfaces (a reviewer reject, a guardrail
   block, an escalation, a reasoned retry), adjudicated deterministically from traces
   against per-framework mappings published *before any data existed*. A separate
   soft tier — a cross-lineage LLM judge ruling that some component verbally noticed
   the fault without acting — is reported alongside and never blended in. By
   construction, judge unreliability cannot move the headline.
2. **Detected vs. reacted vs. recovered, kept separate.** Prior work often folds
   detection into recovery or bundles detection with reaction. Sabot publishes the
   funnel disaggregated, which is what exposes the dominant outcome (section 5).
3. **Pre-registration throughout.** Interpretation bands were committed publicly
   before measurement; seeds were registered publicly before any scored run;
   detection-act mappings shipped in the day-one public stake; all amendments are
   dated, versioned, and logged. There is no file-drawer branch: the frozen
   specification commits to publishing regardless of outcome.
4. **A comparative scoreboard on production frameworks**, with per-component
   attribution, rather than accuracy aggregates on academic systems.

**Honest positioning.** Sabot invents neither fault injection for agent systems,
agent-level mutation scoring, nor the model-swap operator. MAS-FIRE [1] measures
own-mechanism fault detection-and-response on academic multi-agent systems;
AgentAssay [2] formalizes an agent mutation score with model-swap and
version-downgrade operators under external adjudication. Sabot is a synthesis of
those two ideas — own-checks adjudication and mutation-style operators — measured
comparatively at production-framework scale with the additional separations listed
above. Section 2 details what each prior artifact does and precisely how Sabot
differs.

## 2. Related work

**MAS-FIRE** (arXiv 2602.19843) defines an Occurrence Rate (O_f) quantifying a
system's ability to detect injected anomalies and activate fault-tolerant responses,
over 15 fault types on three academic systems (MetaGPT, Table-Critic, CAMEL), with
the system's own mechanisms as the detector. Sabot differs by separating detected
from reacted (O_f bundles them), attributing detection to named guardrail components,
adding no-act "noticed" as its own judged tier, and targeting production frameworks
with published comparative results.

**AgentAssay** (arXiv 2603.02601) formalizes an agent mutation score — stochastic
verdicts, kill criteria — including model-swap (`m_swap`) and version-downgrade
(`m_version`) operators, with kill adjudication by an external harness. Sabot differs
by scoring the pipeline's *own* checks rather than external adjudication, and by the
deterministic-act vs. judged-notice firewall.

**AgentTelemetry** (AIware 2026, DOI 10.1145/3805760.3814931) measures fault
detection via external telemetry layered onto pipelines; Sabot scores only what the
pipeline's own components catch. **AgentCollabBench** (arXiv 2605.08647) measures
fault propagation via seeded false facts (the source of Sabot's O5 mechanism,
credited); Sabot scores whether propagation is *caught*. **ReliabilityBench**
(arXiv 2601.06112) benchmarks agent reliability under stress as a unified surface;
Sabot isolates and headlines own-mechanism detection specifically. **"Failing
Tools"** (OpenReview j7YsSnA64D) scores a single agent's detection of and recovery
from runtime tool failures (the source of Sabot's O2 mechanism, credited); Sabot
targets multi-agent pipelines with per-component attribution. **AutoInject**
(arXiv 2408.00989) injects mistakes into agent messages and reports up to 96.4%
recovery of errors via an added Inspector agent — an end-task recovery figure, not a
detection rate; Sabot's recovery-without-detection metric exists precisely to keep
those two quantities separate. **agent-chaos** and **BalaganAgent** ship
chaos-injection mechanics without a standardized scored metric (agent-chaos's
`tool_mutate` is the source of Sabot's O1 mechanism, credited); the **Owotogbe
proposal** (arXiv 2505.03096) is proposal-stage. A sweep of twelve commercial
evaluation/guardrail vendors found none that injects faults and scores the customer
pipeline's own checks, and none shipping a model-swap chaos operator.

## 3. Method

The frozen specification (SPEC v0.1.x, public repository, tagged) is normative; this
section summarizes it.

### 3.1 The funnel

Every injected fault receives verdicts on three axes:

- **DETECTED_HARD** (headline): a detection act by the pipeline's own surfaces — a
  reviewer/critic reject, a guardrail block, an explicit escalation/interrupt, or a
  retry with reason — adjudicated deterministically from traces against the published
  per-framework mapping. No LLM opinion is involved in this tier.
- **DETECTED_SOFT**: a cross-lineage judge rules that some component verbally noticed
  the fault without an accompanying act. Reported separately, never blended.
- **REACTED**: corrective action causally downstream of a detection.
- **RECOVERED**: the end output passes the same deterministic criterion as the
  no-fault baseline.

Two derived quantities are published per row: the **override gap** (soft-tier notice
rate minus hard-tier detection rate — faults a component saw and the system overrode
anyway) and **recovery-without-detection** (recovered with neither hard nor soft
detection — the task came out right while nothing caught the fault).

```
Sabot Score = |DETECTED_HARD| / |valid injected faults|
```

### 3.2 Validity and exclusions

A run is valid only if its no-fault baseline (same framework, config, task, seed)
passes the task. Invalid runs are excluded, itemized, and published under exactly
three codes — `BASELINE_FAIL`, `RUN_ERROR`, `INJECTION_UNVERIFIED` — with precedence
`RUN_ERROR > BASELINE_FAIL > INJECTION_UNVERIFIED` when a run qualifies for more than
one (SPEC v0.1.3). There are no adjusted scores. An operator whose injection cannot
be verified as landing produces an exclusion, never a fake miss.

### 3.3 Fault operators

Six operators, one fault per run, each with pre-registered per-task ground-truth
notes: **O1 tool-lie** (plausible corruption of a tool result), **O2 false-success**
(a component reports success for work not done), **O3 message-alteration** (one
inter-agent message altered in transit), **O4 model-downgrade** (one agent's model
silently swapped to a weaker same-generation tier, `gpt-5.6-terra` →
`gpt-5.6-luna`), **O5 stale-context** (superseded/contradictory context fed to one
agent), **O6 silent-noop** (a side effect reported done but never performed).
Mechanism credits: O1 cf. agent-chaos `tool_mutate`; O2 cf. "Failing Tools"; O3 cf.
MAS-FIRE routing manipulation; O4 cf. AgentAssay `m_version`; O5 cf.
AgentCollabBench.

### 3.4 Frameworks, configurations, mappings

Three frameworks at pinned versions — LangGraph 1.2.9, CrewAI 1.15.5,
AutoGen/Magentic-One 0.7.5 (maintenance-mode lineage, pinned deliberately for its
doc-verified ledger observability; Microsoft agent-framework is the named wave-2
candidate) — each in a default and a best-documented-guardrail configuration, all
running one uniform pipeline model (`gpt-5.6-terra`) at its default temperature (the
only temperature the model accepts; verified live and documented).

For each framework the exhaustive list of surfaces whose events count as hard-tier
acts was published before data collection: reviewer verdict-token rejects,
deterministic validator/guardrail failures, escalation interrupts, reasoned retries,
and — for Magentic-One, which has no reviewer stage — the orchestrator's stall
re-plan as recorded by the framework's own trace logger. Where the specification's
generic act wording and a published mapping diverge, the pre-registered mapping
governs adjudication and the divergence is disclosed (SPEC v0.1.3; the one known
divergence materially affects one row and is analyzed in section 6). A fairness rule
constrains deterministic guardrail code inside pipelines to checking only the task's
published output contract — the semantic oracle that decides whether a fault was
caught lives only in the scorer (one disclosed asymmetry: section 8, T2).

### 3.5 Tasks, seeds, scale

Five tasks shared across frameworks, each with a deterministic pass criterion and
hand-written anti-memorization twists: research-summarize-review (T1), codegen with
reviewer (T2), data extraction (T3), multi-step planning with tool use (T4), document
QA with citation check (T5). The full matrix is 3 frameworks × 2 configs × 6
operators × 5 tasks × 5 seeds = 900 fault runs plus 150 baselines. Seeds were
registered publicly before any scored run.

### 3.6 Soft-tier judge

The judge is cross-lineage relative to the pipeline model (Claude, claude-opus-4-8),
runs sandboxed with a live sandbox assertion and content canary per batch, sees the
internal transcript plus the operator's ground-truth note, and outputs a structured
verdict. 139 cells (20%) were double-judged with a prompt variant; Cohen's kappa is
published. The headline contains no judge output by construction.

### 3.7 Pre-registered interpretation bands

Committed publicly before any measurement: median hard-tier score below 0.50 ⇒ "full
push"; at or above 0.50 ⇒ publish with the honest "guardrails mostly work" finding.
Publish-regardless is absolute.

## 4. Results

**Headline: median hard-tier Sabot Score across frameworks (configs pooled) =
16.7%.** Per-framework pooled: LangGraph 47/282 (16.7%), CrewAI 51/258 (19.8%),
AutoGen 35/288 (12.2%).

| framework | config | valid | hard | soft notice | override gap | recovery | recovery w/o detection |
|---|---|---|---|---|---|---|---|
| LangGraph | default | 150 | 18.0% | 20.0% | 2.0% | 74.7% | 58.0% |
| LangGraph | guardrail | 132 | 15.2% | 17.4% | 2.3% | 75.8% | 60.6% |
| CrewAI | default | 132 | 18.2% | 18.9% | 0.8% | 74.2% | 56.8% |
| CrewAI | guardrail | 126 | 21.4% | 22.2% | 0.8% | 72.2% | 53.2% |
| AutoGen | default | 138 | 21.0% | 24.6% | 3.6% | 72.5% | 54.3% |
| AutoGen (Magentic-One) | guardrail | 150 | 4.0%† | 15.3% | 11.3% | 60.0% | 51.3% |

† Upper bound; structurally confounded — do not read this cell without section 6.
The reaction column equals the hard column in every row of wave-1 data (every
detecting run's act was itself corrective) and is omitted here; the scoreboard
publishes it in full.

**Exclusions.** 72 of 900 fault runs excluded, all `BASELINE_FAIL`, all on T4 (the
planning task): the pipelines' own no-fault baselines failed the task, so those cells
cannot score detection. The 72 collapse to ~12 independent seed failures replicated
across the operators sharing each baseline, with one dominant signature: the planner
answers a fuel-range rejection by adding a second, illegal refuel, and exhausts its
retry budget. Zero `RUN_ERROR` and zero `INJECTION_UNVERIFIED` exclusions in the
published dataset. The full per-cell appendix is published.

**Judge reliability.** Cohen's kappa 0.826 over 139 double-judged pairs (above the
0.7 full-confidence threshold); zero judge exclusions.

**Guardrails vs. defaults.** The best-documented-guardrail configuration does not
materially outperform the default anywhere: LangGraph's guardrail row is *lower*
(15.2% vs 18.0% — its deterministic validator adds contract checking, not fault
detection, while its exclusions remove T4 cells the default row scores on), CrewAI's
is modestly higher (21.4% vs 18.2%), and AutoGen's comparison is structurally
confounded (section 6). Nothing in wave 1 supports "add the documented guardrail
config and injected faults get caught."

**Pre-registered band.** 16.7% falls in the full-push band (below 0.50), committed
before measurement.

## 5. The dominant outcome: recovery-without-detection

In every one of the six scoreboard rows, the single most common outcome for an
injected fault — 51% to 61% of valid cells, ~830 valid faults overall — is that the
task output is *correct* while *nothing* in the pipeline flags the fault: no hard
act, no judged verbal notice. The pipeline absorbs the sabotage silently.

This is the number the funnel's separations exist to expose. An accuracy-only
evaluation of these same runs would report 60–76% task success and conclude the
pipelines are robust. A detection-bundled-with-recovery metric would blur the same
cells into partial credit. Kept separate, the picture is: **recovery is common,
detection is rare, and most recovery happens without detection.**

Trace analysis identifies the mechanism: the pipeline model notices the anomaly and
routes around the fault without emitting any act. In Magentic-One's override-gap
cells (17 cells where the judge confirmed a verbal notice but no act fired), the
orchestrator's own fact sheet or ledger records the discrepancy and its next worker
instruction simply resolves it inline — correct value used, nothing reported, no
re-plan triggered (zero post-injection re-plans across all 17 cells). The checks are
not failing to see the fault; the system's architecture gives seeing no place to
become acting.

Two operational consequences follow. First, "the task succeeded" is not evidence
that "the checks work" — the majority of successful faulted runs here carry an
undetected fault. Second, silent robustness is fragile robustness: a pipeline that
routes around anomalies without reporting them provides no signal for the cases it
fails to absorb, no audit trail, and no learning loop.

## 6. Case study: the Magentic-One guardrail row, and why 4.0% must not be quoted naively

The most headline-friendly number in the table — the "guardrail" configuration that
detects at 4.0% against its own default's 21.0% — is exactly the number our
adversarial QC attacked first, and it does not survive unqualified. Two findings,
both published as scoreboard footnotes:

**Structural landing (footnote 4).** In the Magentic-One configuration, three of the
six operators (O2, O3, O6) land after the team run has completed — no framework
component executes with the fault in view, so hard-tier detection is structurally
impossible on those 75 cells. On the operator subset where both AutoGen
configurations can structurally detect (O1/O4/O5), they are indistinguishable:
default 6/69 (8.7%) vs guardrail 6/75 (8.0%). **The 21.0%-vs-4.0% spread is
pipeline shape, not detection quality.**

**Stall noise (footnote 5).** All six hard detections in the row are Magentic-One
stall re-plans on T3 whose recorded reasons never reference the injected anomaly —
and clean-run T3 baselines reproduce the same stall re-plans in three of five seeds.
They count under the pre-registered mapping (which cannot be narrowed post-hoc), but
under the specification's stricter "retry with a reason referencing the anomaly"
reading they would not. **4.0% is an upper bound; the honest point estimate of true
hard-tier detection in this configuration is ~0%.**

We publish the row with both footnotes rather than either dropping it (the mapping
was pre-registered; the data is the data) or headlining it (it would be the most
quotable and least true number in the paper). It is also the clearest illustration of
why per-component attribution and structural carve-outs belong in this kind of
measurement: a naive comparative reading would score Magentic-One's orchestration as
five times worse than a round-robin critic, when the honest statement is that its
architecture gives most faults nothing to land in front of, and its apparent
detections are noise.

## 7. Instrument integrity: the benchmark caught its own contamination

A benchmark about whether systems catch their own faults should disclose whether it
catches its own. Proactively:

**Judge-path contamination, caught by the instrument's canary.** The soft-tier judge
runs inside a sandbox with a per-batch sandbox assertion and a content canary. During
the wave-1 judge run, the strengthened canary fired: a user-level retrieval hook in
the operator's local environment was injecting knowledge-base content into headless
judge calls (the canary string had been published in a planning document that the
local index ingests — which is how it was caught). The judge subprocess was
hook-isolated (harness commit `b43dcd7`), and all 535 pre-isolation verdicts were
re-judged under the fixed instrument: 6 changed in any field; exactly 2 flipped the
substantive `noticed` verdict, **both false→true** — the contamination had been
*suppressing* notices, not inflating them. A residual rare context event (~1 in 30
probes, cause not introspectable; 24/24 random-content probes confirm no actual file
reads) was contained by requiring every scored batch to sit inside a window bounded
by two clean probes, with alarmed batches quarantined and re-judged. Every published
soft-tier verdict sits inside a double-clean window. The headline is unaffected by
construction (no judge output reaches the hard tier).

**Infrastructure trail.** Two upstream API quota outages interrupted the matrix run;
179 affected cells were quarantined and re-run clean rather than excluded — zero
`RUN_ERROR` exclusions appear in the dataset. The quarantine directories ship in the
evidence package.

**Adversarial pre-publication QC.** Before this reveal, four QC passes — each an
independent implementation within the project (separate agents, fresh code; not
third-party replication) — ran against the frozen dataset: a from-scratch scoreboard recompute (48/48 published
numbers match; kappa reproduced bit-for-bit), an exclusion-genuineness audit (all 72
verified by independently re-running the committed plans through the deterministic
checker), a directed attack on the most quotable row (section 6), and a
specification-vs-code conformance audit (findings in section 8). The full QC ledger
is published. Wave-1 findings were resolved by disclosure only — the instrument was
not modified after data collection, and by rule may not be.

## 8. Limitations

1. **One pipeline model.** Every result is for `gpt-5.6-terra` at its default
   temperature. Detection rates are plausibly model-dependent; wave-1 claims are
   about these frameworks *with this model*, not about the frameworks in the
   abstract.
2. **T2 guardrail asymmetry (disclosed).** T2's published output contract — alone
   among the five tasks — requires substrings that are canonical answer values, so
   the T2 guardrail configuration's deterministic contract check partially encodes
   the semantic oracle the fairness rule intends to keep out of pipelines. This can
   inflate T2-guardrail hard detection for value-targeting operators (scoreboard
   footnote 7; SPEC v0.1.3). Wave 2 restructures that guardrail to structural
   checks.
3. **Magentic-One structural zeros.** 75 of the guardrail row's 150 cells cannot
   structurally detect (section 6); comparisons against that row must use the
   comparable subset.
4. **Mapping-vs-wording divergence.** The pre-registered AutoGen mapping counts
   stall re-plans without anomaly-referencing reasons; the row it affects is
   published as an upper bound with both readings (section 6, SPEC v0.1.3).
5. **Reviewer prompt pre-checks (T2/T5).** Deterministic pre-check notes derived
   from task assets flow into reviewer prompts in all configurations — an intended
   injection surface for O2, disclosed for completeness.
6. **O4 landing verification.** The model-downgrade operator records
   verified-injection unconditionally (the swap is applied at client construction;
   there is no per-run landing probe). A landing check is added in wave 2.
7. **Conformance nits with no wave-1 impact (verified).** The AutoGen `block`
   surface regex is broader than the published wording (no cell detects on block
   alone, so no number moves); `reacted` is derived as identical to `detected`
   (verified correct cell-by-cell for wave-1 data: every detecting act was itself
   corrective). Both are tightened in wave 2 rather than silently edited now.
8. **Five seeds, one seed set.** Registered before running, but a single set;
   per-row rates carry the usual small-n width. The exclusion appendix shows T4
   validity is seed-driven.
9. **AutoGen lineage.** `autogen-agentchat` 0.7.5 is a maintenance-mode lineage,
   pinned deliberately for reproducibility and ledger observability; results may
   not transfer to Microsoft's successor framework (named wave-2 candidate).
10. **Judged soft tier.** Everything above the hard tier depends on an LLM judge —
    mitigated by cross-lineage choice, sandboxing, double-judging (kappa 0.826),
    and by the headline's independence from it.

## 9. Future work

Wave 2, under a dated v0.2+ specification revision: an **anomaly-first reporting
protocol** — requiring pipelines to report noticed inconsistencies before emitting
verdicts or artifacts — for which a pre-registered probe on held-out branches showed
promising early signal (the probe and its results publish with the wave-2 paper,
released alongside this one); Microsoft
agent-framework as the successor AutoGen
lineage; the T2 guardrail restructure, O4 landing probe, block-regex tightening, and
independent `reacted` derivation listed above; additional frameworks (OpenHands) and
operators; and multi-model replication of the wave-1 matrix.

## 10. Reproducibility and evidence package

The public repository (`github.com/Jott2121/sabot`) carries: the frozen
specification with its complete dated amendment log (v0.1 → v0.1.3), pre-registered
seeds (committed before any scored run), task specifications with per-operator
ground-truth notes, the full scoring harness (Apache-2.0) with its mutation-testing
receipts, the raw trace corpus for all 1,050 runs including baselines, the
quarantine directories from both infrastructure incidents, the pre-publication QC
ledger, and the scoreboard with its complete exclusion appendix. The hard tier is
re-computable from traces with no LLM: the recompute path is deterministic
end-to-end.

## References

[1] Jia, Deng, Chen, Wang, Zheng. MAS-FIRE: Fault Injection and Reliability
    Evaluation for LLM-Based Multi-Agent Systems. arXiv:2602.19843.
[2] Bhardwaj. AgentAssay: Token-Efficient Regression Testing for
    Non-Deterministic AI Agent Workflows. arXiv:2603.02601.
[3] AgentTelemetry. AIware 2026. DOI 10.1145/3805760.3814931.
[4] Mazumder et al. AgentCollabBench: Diagnosing When Good Agents Make Bad
    Collaborators. arXiv:2605.08647.
[5] Gupta. ReliabilityBench: Evaluating LLM Agent Reliability Under
    Production-Like Stress Conditions. arXiv:2601.06112.
[6] Failing Tools: Benchmarking LLM Agent Recovery Under Runtime Tool Failures.
    OpenReview j7YsSnA64D.
[7] On the Resilience of LLM-Based Multi-Agent Collaboration with Faulty Agents
    (AutoInject). arXiv:2408.00989.
[8] Owotogbe. Assessing and Enhancing the Robustness of LLM-based Multi-Agent
    Systems Through Chaos Engineering. arXiv:2505.03096.
[9] agent-chaos; BalaganAgent (chaos-injection tools, alpha repositories).
