# The Checks Were Decorative — and the Fix Is Measurable: Anomaly-First Reporting in Multi-Agent Pipelines

**Sabot wave 2: a pre-registered, same-cell paired protocol experiment**

Jeff Otterson
`github.com/Jott2121/sabot` — spec/results CC BY 4.0, harness Apache-2.0

*Version 1 — 2026-07-24. Numbers are locked against the pre-publication QC
ledger (`docs/qc-wave2-2026-07-24.md`); every footnoted caveat in that ledger
travels with the number it qualifies. The complete evidence package — the frozen
specification (v0.2.0, tagged before any wave-2 scored run), the pre-registered
seeds and all 30 anchors, the harness, the full raw-trace corpus, both
quarantine directories, and the QC ledger — is public at
`github.com/Jott2121/sabot`, together with the wave-1 preprint this paper
extends.*

> **Post-publication statistical supplement (dated note, 2026-07-25).** Every
> number in this paper is a point estimate; a statistical supplement published
> after this paper's release (`harness/runs/wave2/UNCERTAINTY.md`, regenerable
> offline via `scripts/score_uncertainty.py --check`) adds exact
> replicate-cluster bootstrap intervals for every headline figure — e.g. the
> 55.0% median carries a 95% CI of [52.3, 58.0] against wave-1's 16.7% [15.6,
> 17.8], and the per-cell paired effect is +39.4 pp [+37.0, +41.4]. Two of its
> findings qualify this paper's framing: (1) the five standard framework rows
> are NOT a ranking — all ten pairwise interval contrasts contain zero; (2) the
> replicate labels this paper calls "seeds" (11-15) were never passed to the
> model or any RNG — they are labels on five stochastic repetitions, and the
> supplement restates the analysis accordingly. The supplement, the strict
> injection-evidence floor as committed code, and the prospective rule
> adoptions from these findings ship as SPEC v0.2.1 (see the SPEC Amendment
> log); this paper's text and numbers are unchanged. One instrument defect
> found by the v0.2.1 anchor-collision review is disclosed with a sensitivity
> bound: the T3 adapters serve the task file's ground-truth section to the
> pipeline (both waves), so T3's reviewer had the fault catalog in view;
> excluding every T3 row moves the headline median only from 55.0% to 53.6%
> (QC ledger addendum, 2026-07-25).

---

## Abstract

Wave 1 of Sabot measured whether production multi-agent frameworks' own checks
detect injected faults: median hard-tier detection was 16.7%, and the dominant
outcome — 51-61% of valid faults in every row — was recovery-without-detection:
the pipeline model noticed the fault and routed around it, because no pipeline
ever asks it to report before repairing. Wave 2 tests the implied fix. The
anomaly-first protocol adds one requirement at the review seam: report every
noticed inconsistency, quoting exact conflicting values, BEFORE emitting a
verdict or artifact. We re-ran the full wave-1 matrix — same frameworks, configs,
tasks, operators, and seeds; 825 fault runs plus 150 re-baselined controls — with
that single change, under adjudication rules, anchors, and five predictions
pre-registered publicly before any scored run. Hard-tier detection (frozen wave-1
mapping OR an anchored FLAGS report) rose from 15-21% to 53-56% on every
standard scoreboard row (strict injection-evidence floor: 48-52%), and from
approximately zero to 73.6% (strict floor 55.6%) on the Magentic-One
configuration once its reporting requirement was integrated into the task's
output contract rather than appended as an instruction. The negative results are reported with equal prominence: the
FLAGS surface carries no signal for silent model downgrades (indistinguishable
from its 26% clean-baseline false-anchor base rate), the output-contract change
itself perturbs the Magentic orchestrator (clean-run stall re-plans rise 3/25 to
18/25 seeds, inflating its non-FLAGS surface with noise we quantify and
discount), one previously-at-ceiling cell class got worse, and reporting is not
reacting — flag-only detections carry no corrective act, so the
notice-without-act phenomenon wave 1 named migrates onto the new surface rather
than disappearing. All raw traces, both quarantine trails — one from a mid-run
quota outage and one from a mid-run breach of the judge's own tool sandbox that
the instrument's canary caught (section 6) — a 189/189 recompute by an
independent implementation within the project, and the adversarial QC ledger
publish as the evidence package.

## 1. Introduction

Wave 1's central finding was not the 16.7% headline but the mechanism behind the
misses: in every configuration, the majority outcome was a correct final output
with no detection anywhere — and the traces showed the pipeline model noticing
the planted anomaly, then resolving it inline without emitting any act. The
checks were not blind; the protocol gave noticing nowhere to go.

That reading makes a falsifiable claim: if the miss is protocol rather than
capability, then requiring the pipeline to report noticed inconsistencies before
proceeding should recover a large fraction of the misses — and if it is
capability, it should not. Wave 2 runs that experiment at matrix scale as a
paired intervention: one change, everything else frozen, every comparison
same-cell against wave 1.

Contributions: (1) a pre-registered protocol treatment measured on 825 paired
cells across three production frameworks; (2) a deterministic adjudication
method for free-text anomaly reports — pre-registered anchor substrings tying a
report to THE planted fault — published together with its measured clean-baseline
false-anchor base rates, which we argue any text-matching detection metric owes
its readers; (3) the format-contract rule for orchestrator pipelines (protocol
requirements survive orchestrator re-writes only as output-format requirements);
(4) negative results with parity of prominence, per the pre-registered
publish-regardless commitment.

## 2. The anomaly-first protocol (SPEC v0.2.0, pre-registered)

One change per pipeline, at the review seam. Where a verdict-token
reviewer/critic exists, its system prompt gains a fixed addendum: the reply must
contain exactly one line "FLAGS: <every inconsistency noticed, quoting the exact
conflicting values or names>" — or "FLAGS: none" — BEFORE the verdict line.
Magentic-One has no reviewer stage; there, the FLAGS line is specified as line 1
of the task's OUTPUT CONTRACT itself, and the harness strips it before the frozen
wave-1 parsers run, so task scoring is byte-identical. The contract placement is
the format-contract rule, learned from the pilot: strict output contracts
("raw JSON only") survive orchestrator re-writes while side instructions do not.

Adjudication is deterministic end-to-end. A FLAGS line at or after the injection
is a detection act iff it is non-"none" AND contains a pre-registered anchor
substring for that (task, operator) — the anchors, all 30 cells, were published
in the tagged spec before any run, derived from the frozen operator ground
truth: the conflicting values for value-faults, the injected fake-success text
for absence-faults. The wave-2 headline is the UNION: the unchanged wave-1
mapping OR an anchored flag. The judge-free-headline property carries over.

## 3. Experimental design

Same three frameworks at the same pins, both configs, five tasks, six operators,
and wave-1's registered seeds reused verbatim, so every comparison is same-cell
paired. Baselines re-run under v0.2 prompts. One pre-registered structural
carve-out: Magentic-One x {O2,O3,O6} (75 cells), faults that land after the run
ends (wave-1 footnote 4) — 825 fault runs + 150 baselines. Four instrument
corrections closing wave-1's disclosed findings shipped as new dated code (T2
structural guardrail; O4 landing probe; block-surface exact match; independent
reacted derivation). Five predictions pre-registered with an explicit
null-result publication commitment.

## 4. Results

**Headline (pooled union, configs pooled per framework): LangGraph 55.0%, CrewAI
53.5%, AutoGen 65.3%; median 55.0% — against wave-1's 16.7%.** An independent
implementation within the project — fresh, spec-transcribed code reading only
the raw traces — reproduced all 189 published rows and every aggregate exactly.

| row | wave-1 hard (paired) | wave-2 union | strict floor |
|---|---|---|---|
| LangGraph default | 17.4% | 55.1% | 47.8% |
| LangGraph guardrail | 15.1% | 54.9% | 48.6% |
| CrewAI default | 18.2% | 53.3% | 51.3% |
| CrewAI guardrail | 21.4% | 53.6% | 52.2% |
| AutoGen default | 20.5% | 55.6% | 52.8% |
| AutoGen Magentic guardrail | 8.3%† | 73.6%‡ | 55.6% |

† True wave-1 detection ~0% (wave-1 footnote 5). ‡ The honest reading: flags-only
union; 84.7% arises only under the permissive pre-registered mapping whose
magentic acts are 100% stall noise (section 5.2). The strict floor counts only
flags quoting injection-only tokens — a deliberate under-count discarding genuine
paraphrase detections; truth lies between floor and published.

**Per-operator lift is where the mechanism shows.** Two populations appear in this
paragraph and are labelled where they differ: *reviewer-bearing rows* (the five
configurations that have a verdict-token reviewer, excluding the Magentic
carve-out) and *all rows* (every valid cell). Tool-lies (O1): anchored detection
92.4% on reviewer-bearing rows (93.7%, 134/143, across all rows) against a 32.7%
clean base rate, with 132 of those 134 all-row anchored cells quoting the
injected-only value — the protocol works close to ceiling where a contradiction
is in view. Stale context (O5): anchored detection 87.4% on both populations
against a wave-1 paired hard rate of 0.8%, a lift of +86.7 points, with 110 of
the 125 all-row anchored cells quoting stale-sheet-only content; the
metadata-echo alternative explanation fails
(values-only adjudication moves the rate 3.5 points). False-success (O2): +18.5
points, and every sampled anchored flag both quotes the fake claim and
challenges it. Message alteration (O3) was already near ceiling and stays there
— with one regression (section 5.4). Silent no-ops (O6): no lift, as predicted
(P4): an absence offers nothing to quote. Model downgrade (O4): the apparent
lift is entirely spurious (section 5.3).

**The protocol changes behavior, not just reporting.** On reviewer rows the
frozen wave-1 mapping surface itself rose (15-21% to 19-29% on wave-2 runs):
sampled acts are genuine anomaly-referencing rejects — asking for flags first
makes reviewers act more, the pilot's T2/O1 observation at scale.

**Magentic-One is the strongest and the most caveated result.** Under the
contract-integrated FLAGS, the configuration whose true wave-1 detection was
approximately zero produced anchored reports in 73.6% of cells (P3 confirmed:
T1, the pilot's format-contract failure case, went 0/5 to 5/5, every flag
quoting the injected-only value). Every caveat this row carries is in section 5.

**Soft tier.** The cross-lineage judge (union-false cells, N=336, plus a
deterministic 20% double-judged) reproduced at Cohen's kappa 0.767 — above the
0.7 full-confidence threshold — with zero judge-exclusions. Adding judged
verbal notices to the hard-tier union raises the total notice rate to 65.5%
(from 57.3% union), an 8.3-point override gap: faults a component verbally
noticed and the pipeline acted on in neither surface. The Magentic guardrail row
reaches a 100% soft-notice rate — the orchestrator sees essentially every fault
and reports or acts on far fewer.

## 5. Negative results and discounts (pre-registered prominence)

**5.1 Reporting is not reacting (P5).** Reacted derives from corrective acts,
and a FLAGS line is a report: flag-only detections carry reacted=false. On
standard rows, roughly half the union consists of such cells; on Magentic, the
honest reacted rate under the narrow reading is 0%. Wave 1's dominant outcome,
recovery-without-detection, falls from 51-61% to 26.1% on the union surface and
22.1% counting the judged soft tier — but is 50.0% on the frozen mapping
surface, essentially unchanged from wave 1. Read together (P5): the protocol
makes the pipeline REPORT the faults it was silently absorbing, but it does not
make the pipeline ACT on them at anything like the same rate. The
notice-without-act phenomenon wave 1 named does not disappear under
anomaly-first reporting — it becomes legible. The pipeline now tells you what it
sees and still does not act. We regard this as the protocol doing exactly and
only what it promised, and as the sharpest open problem it exposes.

**5.2 The contract perturbs the instrument it instruments.** Magentic clean-run
baselines stall-replan in 18/25 seeds under the v0.2 output contract versus 3/25
in wave 1. Consequently the row's non-FLAGS mapping surface (59.7%) tracks the
baseline stall pattern, not the faults — all 43 mapping acts are stall-ledger
booleans, zero reference the anomaly, and the section-2 narrow reading scores
the surface 0/72. Both readings publish; the quoted number (73.6%) excludes the
noise entirely. Measuring a system by changing its output contract changes the
system; any protocol-level intervention on orchestrator pipelines owes its
readers this baseline comparison.

**5.3 The O4 surface is dead, and the base-rate table says why.** Anchored-flag
rates on clean baselines (no fault present): O1 32.7%, O4 26.0%, O5 24.0%, O3
12.7%, O2 5.3%, O6 1.3% — several tasks deliberately embed natural
discrepancies whose values are registered anchors, and diligent reviewers flag
them. For O1/O5 the fault-run rates (92%, 87%) tower over base; for O4 the
fault-run rate (24.5%) IS the base rate — a silent downgrade injects no content
to quote, so the flags surface detects nothing, and the honest O4 number is the
mapping-only 9.8%. Any anchored-text detection metric should publish this table;
ours would have looked 23 points better on O4 without it.

**5.4 A ceiling cell got worse (P2 violation).** langgraph/guardrail/T5/O3:
5/5 in wave 1, 3/5 union in wave 2 — in the lost seeds the reviewer's FLAGS
line affirmatively asserts the fault is absent, then approves. A mandated
report can anchor a reviewer into confidence. One cell class, disclosed.

**5.5 Minor disclosures.** The registered T4/O1 anchor "40 km" is a substring of
the true "140 km", contradicting the spec's own bare-40 note (zero numeric
impact — "140" fires on the same texts). In Magentic cells the FLAGS emitter is
the orchestrator-worker system, not the worker alone. Six spec-wording
underdeterminations found by the recompute are listed in the QC ledger; the
scorer's choices coincided with the spec-transcribed recompute on all six.

## 6. Instrument integrity

Mid-run, the OpenAI account exhausted its quota; 11 Magentic baselines and their
33 dependent cells died on 429 errors. All 44 artifacts were quarantined —
preserved as evidence, never recorded as exclusions — and re-run clean after
refunding: the published dataset contains zero RUN_ERROR cells and 39
BASELINE_FAIL exclusions (the planner-task class wave 1 documented, here
slightly fewer). The environment repeatedly killed long-running drivers; the
crash-safe resume design made every interruption loss-free, and the ledger
records every attempt.

**The judge's own sandbox was breached mid-run, and the instrument caught it.**
At batch 5 of the first judge run the pre-batch content canary fired: the judge
model had reached the filesystem through a tool added to its harness *after* this
benchmark's deny list was frozen, and its probe reply quoted the canary contents
verbatim while naming the method it used. The instrument refused to run — the
fail-loud path held. This is the benchmark's second self-catch of its own
contamination; wave 1's canary caught a retrieval hook injecting content into
judge calls, and wave 2's caught deny-list decay against an evolving harness. The
closure was to stop enumerating what to forbid and pin an empty allowlist
instead, with the deny list retained only as defense in depth. The probe itself
was redesigned into a two-arm config-drift gate: a permissive arm with tools
enabled must retrieve a fresh random per-run token, making the content-absence
criterion falsifiable in the passing direction, while the restricted judge-config
arm must not. The old refusal-phrase criterion was dropped as noise, since a
toolless model narrates hallucinated tool transcripts roughly half the time and a
flapping gate gets disabled. All 100 pre-fix verdicts were quarantined and the
entire judged set re-ran from zero under the fixed instrument, following wave-1's
535-verdict re-judge precedent; every soft-tier number in this paper comes from
the re-run. The honest scope, stated in the code: this is config-drift regression
detection, not a containment proof. **The standing lesson generalizes past this
benchmark: a deny list against an evolving tool surface decays silently, so pin
allowlists.**

Total wave-2 pipeline spend: $33.47 on the margined circuit-breaker meter against
a $38 cap that never tripped (958 paid runs; derivation and per-profile counts in
the published spend ledger). That meter is a proxy, not a bill: the wave-1
dashboard reconcile measured it understating real billing by roughly 15%, so the
honest expectation is $38-40 real, and a wave-2 reconcile is still outstanding.
The judge tier cost nothing, running on a subscription rather than a metered key.
Build hygiene: a 1,178-mutant gate with 0 survivors (1,175 killed, 3 pre-existing
documented timeouts; receipts in the harness `MUTATION.md`); all four suites
green; an adversarial code review before any paid run; the QC above ran before any
number was quoted.

## 7. Limitations

Wave-1's limitations carry (one pipeline model, five seeds, judged soft tier,
maintenance-mode AutoGen lineage). Wave-2 adds: anchor adjudication is
deterministic but permissive at the registered edges — bounded above and below
by the published/strict pair, with base rates disclosed and the strict floor
recomputable from committed code (`sabot/strict.py`, which persists the anchor-side
classification the first published floor had only stated; recomputing corrected those
floors by +1 to +3 cells on standard rows and -2 on Magentic, and moved no headline).
The strict floor carries two limitations of its own, both measured and published:
it is a lower bound on detection *this anchor set can see*, since three cell classes
have no injection-only anchor at all and score zero there whether or not the pipeline
spoke — so a coverage-adjusted variant is published alongside (73-74% coverage on
standard rows, floor 50.9-56.9% over covered cells) — and the strict rule itself fires
on 4.6% of clean baselines where no fault exists, almost entirely a T3 artifact
(20.0% on T3 against 0.0% on T1, T4 and T5), against 17.0% for the published anchor
rule on the same corpus; the T2 guardrail
restructure makes that row's guardrail-surface acts non-comparable across waves
(reviewer and FLAGS surfaces unaffected); the O4 landing probe can exclude cells
wave 1 counted, so O4 rows are not strictly paired; the union headline is by
construction at least the mapping headline (the wave1-mapping column isolates
the protocol's contribution); soft-tier reliability is kappa 0.767 (full
confidence) over 68 double-judged pairs, and the judge sandbox suffered and
survived a mid-run tool-boundary breach (section 6).

## 8. What follows

v0.2.1 (dated, post-publication): the strict-evidence scorer shipped first, on
publication day, because a sensitivity bound readers are asked to quote should not
rest on an unreproducible analysis (section 7). Still queued: the narrow retry-reason
adjudication; the O4 flags carve-out; an anchor-collision review pass — the strict
recompute confirmed three cell classes whose registered anchors cannot separate
injected from true text, so they score zero at the floor; and the six wording fixes.
Beyond: multi-model replication, Microsoft agent-framework as the successor
lineage, and the obvious engineering question this result raises — if one
prompt-level requirement triples own-check detection, what does a
framework-native anomaly-first stage recover, and at what cost to the
stall-prone orchestration patterns section 5.2 exposed?

## References

As wave-1 preprint (MAS-FIRE arXiv:2602.19843; AgentAssay arXiv:2603.02601;
AgentTelemetry AIware 2026; AgentCollabBench arXiv:2605.08647; ReliabilityBench
arXiv:2601.06112; Failing Tools OpenReview j7YsSnA64D; AutoInject
arXiv:2408.00989; Owotogbe arXiv:2505.03096; agent-chaos; BalaganAgent), plus
the Sabot wave-1 preprint (this repository).
