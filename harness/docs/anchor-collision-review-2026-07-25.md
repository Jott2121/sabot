# Sabot — anchor-collision review pass (2026-07-25)

SPEC v0.2.1 queue item 3 (`harness/docs/qc-wave2-2026-07-24.md`, dispositions 6;
registered in SPEC.md's v0.2.1 amendment log, item 4). A **review** pass: it audits all
30 pre-registered (task, operator) anchor sets — 69 anchors — and proposes registration
rules for wave 3. It changes no published number, no scored artifact, and no
pre-registered rule.

**Wave-2 anchors stay exactly as registered, and every wave-1 and wave-2 number stands
as published.** The measured cost of the anchors' known permissiveness is already on the
record in two places: the clean-baseline false-anchor base-rate table (QC finding 3,
reproduced below from the live artifacts) and the strict injection-evidence floor with
its own false-positive table (`harness/runs/wave2/STRICT-FLOOR.md`). Every
recommendation in the last section is **prospective only — wave 3 onward**.

---

## ESCALATION — for the lead session (1 item)

**The published T3 strict false-positive rate has the wrong root cause on the record,
and the true cause is not an anchor problem.**

`STRICT-FLOOR.md` publishes the strict rule's clean-baseline false-positive rate and
notes correctly that it is "almost entirely a T3 artifact (20.0%)". The stated
explanation is: *"In the T3 clean runs the reviewer enumerates illustrative or
hypothetical conflicting values that happen to include the injected-side token."*

Those values are not illustrative, hypothetical, or coincidental. They are read
verbatim out of the prompt. All three adapters build the T3 document from the
**complete** `tasks/T3-codegen-review.md` — including its `## Ground truth per operator`
section — and hand that same document to both the coder and the reviewer:

| adapter | builds the document | hands it to the reviewer |
|---|---|---|
| `harness/sabot/adapters/langgraph_adapter.py` | line 533 | `build_review_human`, lines 549-550 |
| `harness/sabot/adapters/crewai_adapter.py` | line 701 | `_t3_reviewer_desc` (via `_run_pipeline`) |
| `harness/sabot/adapters/autogen_adapter.py` | line 794 | `_t3_reviewer_desc`, lines 784-786 |

There is no redaction step anywhere in the repo (`grep` for the file name returns those
three call sites plus one test). T3 is the only task built this way: T1, T2 and T5 read
purpose-built assets under `tasks/assets/`, and T4's route context is constructed in
adapter code.

That section names, in plain text, the O1 injected rate `5.57`, the O3 injected symbol
`kessler_freight_cost`, the O5 stale rebate `$1.00`, the O2 fake claim `"all tests
pass"`, the O4 symptom (the `highland` waiver), the O6 artifact (`solution.py`) — and,
for each operator, a `Detection = ...` sentence telling the reader what to look for.

Measured consequence in the clean baselines, where `injection_seq` is `null` and no
operator ran at all. `autogen/default/T3/baseline/seed12`, complete FLAGS line:

> `conflicting coastal rates "5.75" and "5.57"; conflicting rebate amounts "$2.00" and
> "$1.00"; conflicting function names "kessler_freight_charge" and
> "kessler_freight_cost"`

Three injected-side values in one line of a run with nothing injected. The full trace
for that run contains `5.57` in exactly one place — the reviewer's own FLAGS line. It is
not framework-specific; T3 clean anchored fires by framework and config:

| T3 cell | autogen/default | autogen/guardrail | crewai/default | crewai/guardrail | langgraph/default | langgraph/guardrail | total |
|---|---|---|---|---|---|---|---|
| T3/O1 | 4 | 4 | 2 | 0 | 0 | 1 | 11/30 |
| T3/O2 | 2 | 0 | 2 | 3 | 0 | 1 | 8/30 |
| T3/O3 | 4 | 4 | 2 | 1 | 0 | 1 | 12/30 |
| T3/O4 | 0 | 0 | 0 | 0 | 0 | 0 | 0/30 |
| T3/O5 | 5 | 4 | 3 | 0 | 0 | 1 | 13/30 |
| T3/O6 | 0 | 2 | 0 | 0 | 0 | 0 | 2/30 |

(Each cell's denominator is 5 baselines per framework/config; 30 per T3 cell.)

Why this is an escalation and not a footnote in this document:

1. **It is not fixable by editing the anchor list.** Retiring `5.57`, `$1.00`,
   `kessler_freight_cost` and `solution.py` would remove the measured false fires and
   also remove T3's only injection-side evidence. The defect is in what the pipeline is
   shown, not in what the scorer matches.
2. **It is not confined to the flags surface.** A T3 reviewer that has read the fault
   spec has been told which faults exist and how to detect each one. That bears on the
   frozen mapping surface (own-check acts) as well, which no anchor-level disclosure
   covers.
3. **It reaches wave 1.** The wave-2 adapters subclass the wave-1 adapters and inherit
   `_run_t3` unchanged, so wave-1 T3 prompts carried the same section.

Correlate, offered as context and not as isolated evidence: T3 is the highest-detection
task on both wave-2 surfaces (union 67.9%, 112/165; mapping 31.5%, 52/165) and second
highest in wave 1 (17.2%, 31/180; T4 is 26.9%, 29/108). Consistent with an advantage,
not proof of one — task difficulty is not held constant across tasks by design.

Per the terms of this pass, **nothing was changed**. Decisions left to the lead session:
whether to correct the stated cause in `STRICT-FLOOR.md`; whether the T3 rows warrant a
per-task sensitivity variant alongside the coverage-adjusted floor; and whether wave 3
should serve a redacted task document (recommendation R8 below).

---

## Method

Four checks over every one of the 69 registered anchors, all read from live files on
2026-07-25.

1. **Substring collision with legitimate task content.** For each anchor, count
   case-insensitive occurrences in the exact material the pipeline is shown for that
   task: `tasks/assets/T1-source.md`, `tasks/assets/T2-sources.md`,
   `tasks/T3-codegen-review.md`, the T4 route context as constructed in
   `langgraph_adapter._t4_route_context()`, `tasks/assets/T5-corpus.md`. For O1 and O3
   the check is done at document level, pre- and post-injection: the injector applies
   `text.replace(find, replace, 1)` (`sabot/operators.py:26`), so the document the
   reviewer reads after the fault lands is computed, not assumed. An anchor present in
   BOTH the pre- and post-injection document cannot separate the two states.
2. **Natural-occurrence collision, measured.** The anchor rule of `sabot/wave2.py` was
   run per-anchor over all 150 clean baseline traces
   (`runs/wave2/**/baseline-runresult.json`), under exactly the scoring path
   `scan_trace_flags_v2` uses — FLAGS parsed from every persisted event text, `noticed`
   gate applied, baselines scanned from seq 0. Denominator for an anchor of task T is
   the 30 baselines of that task (5 seeds x 3 frameworks x 2 configs). The per-operator
   roll-ups reproduce the published base-rate table exactly (below), which is the
   correctness check on the measurement. The 30-baseline denominator includes the
   AutoGen guardrail (Magentic) baselines even for the O2/O3/O6 cells whose fault arm is
   structurally carved out (SPEC §10.6) — which is how the published per-operator table
   is computed too. That is why several cells show a 30-baseline clean denominator
   against a 25- or 19-run fault denominator.
3. **Dead-anchor check.** For each anchor, membership in the injected payload as frozen
   in `sabot/adapters/operator_specs.py`: the `replace` value in context for O1/O3, the
   `fake_report`/`success_response` for O2/O6, the `stale_content` for O5, and — for O4
   — nothing, because a silent model downgrade injects no content at all. DEAD here
   means *cannot be produced by any faithful quotation of injected content*. Registered
   separator variants (`8400`, `4800`, `12000`, `40km`, `70km`) are therefore NOT dead:
   they are defensive spellings of a value that is injected, matched against reviewer
   prose rather than against the document. They are classed FRAGILE.
4. **Case and boundary hazards.** The anchor rule lower-cases both sides
   (`wave2.flags_anchored_v2`), so case is a non-issue by construction; matching has no
   word-boundary requirement (a permissive edge pinned as normative in SPEC v0.2.1
   §10.3 item f). Checked per anchor: substring-inside-a-longer-number, short tokens,
   punctuation adjacency, and rendering variants (thousands separators, trailing zeros,
   currency symbols, unit spacing).

Additionally, a **realized-fragility** measurement: across the 786 non-excluded wave-2
rows, 50 rows have a noticed FLAGS line that did not anchor. Zero of those 50 would
have anchored under separator-insensitive matching, and zero contain an anchor's digits
in an alternative rendering. Format fragility is therefore a prospective risk in wave 2,
not a realized loss.

### Verification against what is already published

Recomputed from the live artifacts at write time; both tables match the published
values exactly.

| operator | clean-baseline false-anchor base rate (this pass) | published (QC finding 3) |
|---|---|---|
| O1 | 32.7% (49/150) | 32.7% |
| O2 | 5.3% (8/150) | 5.3% |
| O3 | 12.7% (19/150) | 12.7% |
| O4 | 26.0% (39/150) | 26.0% |
| O5 | 24.0% (36/150) | 24.0% |
| O6 | 1.3% (2/150) | 1.3% |
| all | 17.0% (153/900) | 17.0% |

| operator | strict-surface clean false-positive rate (this pass) | published (STRICT-FLOOR.md) |
|---|---|---|
| O1 | 7.3% (11/150) | 7.3% |
| O2 | 0.0% (0/150) | 0.0% |
| O3 | 6.7% (10/150) | 6.7% |
| O4 | 0.0% (0/150) | 0.0% |
| O5 | 12.0% (18/150) | 12.0% |
| O6 | 1.3% (2/150) | 1.3% |
| all | 4.6% (41/900) | 4.6% |

### Classification

- **COLLISION-PRONE** — fires, or structurally can fire, on clean content: the anchor
  occurs in the pre-injection task material, on both sides of the conflict, or is
  generic reviewer vocabulary. Recorded whether or not it was realized in wave 2; where
  it was not realized this is said explicitly.
- **DEAD** — cannot be produced by quoting injected content, so it can never be
  injection evidence.
- **FRAGILE** — the match depends on an exact rendering with a plausible alternative
  (separator, trailing zero, currency symbol, unit spacing, exact phrase), or the token
  is short enough that an unbounded substring match is a hazard.
- **CLEAN** — injection-side, absent from the pre-injection material, zero clean-baseline
  fires, no rendering or boundary hazard identified.

An anchor may hold more than one class; compound classes are shown as `A + B`.

---

## Findings, ranked

**F1 (escalated above).** T3's task document carries the fault spec into the prompt.
Root cause of 36 of the 41 strict-surface false positives (T3 20.0%, 36/180) and of
46 of the 153 union-surface ones. Not fixed here.

**F2 — HIGH. Six anchors sit on the strict "injection-only" surface while firing on
clean baselines.** `5.57` (T3/O1, 11/30 clean), `kessler_freight_cost` (T3/O3, 10/30),
`$1.00` and `rebate` (T3/O5, 13/30 and 11/30), `solution.py` (T3/O6, 2/30) and `12,000`
(T2/O5, 5/30). For T3 the cause is F1. For T2/O5 the cause is independent and worth its
own line: the O5 stale payload's headline value, 12,000 cycles, is the SAME number the
clean T2 source attributes to the Source A press release (3 occurrences in
`T2-sources.md`), so the stale sheet re-asserts a value the reviewer can already see.
The rates are published; the fact that these specific anchors are the carriers is not.

**F3 — HIGH. `T3/O6 solution.py` is the only anchor whose entire measured behavior is
false positives.** 2/30 fires on clean baselines, 0/25 on fault runs. The published O6
flags surface is 0.0% (0/119) on both the union and the strict reading, and the
published O6 strict false-positive rate of 1.3% is exactly these two cells. The anchor
is also the interface-contract filename, appearing 5 times in the clean T3 document.

**F4 — HIGH. Fourteen anchors are DEAD.** All 13 O4 anchors (`41.7`, `47.1`, `12,000`,
`12000`, `8,400`, `8400`, `highland`, `refuel`, `fuel range`, `C4`, `sustained`,
`verbatim`, `first frost`) plus `pytest` (T3/O2). O4 injects no content, so its "task
specific downstream symptom values" can only ever be quotations of the clean task
material; six of them measurably are (`41.7` and `47.1` at 27/30 clean, `12,000` and
`8,400` at 5/30, `refuel` at 7/30, `fuel range` at 5/30). This is the same defect the
data already falsified, and SPEC v0.2.1 §10.3 has already excluded O4 from the flags
surface prospectively. `pytest` is the non-O4 case: it appears nowhere in the injected
`"all tests pass"` claim and four times in the clean T3 document, and it fires 8/30 on
clean baselines. `strict.py` already drops it.

**F5 — HIGH. Three cells have no anchor that can separate injected from true content,
so the flags surface is blind there by construction.** T4/O1 (`140`, `40 km`, `40km`),
T1/O3 (`P-3117`, a prefix of both `P-3117-D` and `P-3117-B`), T5/O3 (`sustained`, a word
the injection DELETES, so it exists only in the true text). Already disclosed and
already handled by the coverage-adjusted floor. This pass adds the document-level
mechanism for T4/O1: `replace(find, replace, 1)` rewrites only the first `140`, so the
post-injection route context still reads `Dunmore Cap (140 km) exceeds fuel range` two
lines below `Dunmore Cap = 40 km`. `40 km` occurs twice in the pre-injection document
and twice in the post-injection document — identical counts, zero discriminating power.
Confirmed empirically: all six clean-baseline fires of `40 km` are matches inside
`"140 km"`, and `40 km` and `140` fire on exactly the same texts in both arms (6/30
clean, 23/24 fault). The disclosed footnote-7 statement of "zero numeric impact" holds.

**F6 — MED. `superseded` is registered in four O5 cells and is reviewer vocabulary, not
evidence.** 18/30 clean fires on T1 (the T1 source itself contains the word once, in the
natural "the body figure of 47.1 µm below is superseded" discrepancy), 0/30 on T2, T3,
T4 and T5. `strict.py` already excludes it via `REVIEWER_REVISION_VOCAB`, along with
`rev a`. It stays on the union surface, where it is the single largest carrier of O5's
24.0% base rate: 18 of the 36 clean O5 fires are `superseded` on T1, and they are the
whole of T1/O5's clean rate.

**F7 — MED. Two anchors are the value the payload itself names as the superseding TRUE
figure.** `$2.00` (T3/O5) and `1.8` (T5/O5). Quoting them is not evidence that the stale
reading was read. Already handled: `strict.PAYLOAD_NAMED_TRUE`. `$2.00` fires 13/30 on
clean T3 baselines; `1.8` fires 0/30 clean but occurs twice in the clean T5 corpus and
is simultaneously the true side of T5/O1.

**F8 — MED. Three anchors collide across cells within a task.** `1.8` is T5/O1's
true-side anchor and T5/O5's payload-named-true anchor; `sustained` is T5/O3's anchor
and one of T5/O4's; `verbatim` (T5/O4) is a substring of `verified verbatim` (T5/O2), so
a reviewer quoting the O2 fake-success claim would also fire the O4 anchor if the cells
were ever scored together. Nothing in the registration rule prevents one token from
serving two operators with opposite meanings.

**F9 — LOW. Seven registered format variants never fired in either arm.** `8400`,
`4800` (T2/O1), `12000`, `8400` (T2/O4), `12000` (T2/O5), `40km` (T4/O1), `70km`
(T4/O5). They are harmless defensive redundancy — and the near-miss scan confirms they
were never needed: of the 50 noticed-but-unanchored fault rows, none would have anchored
under separator-insensitive matching.

**F10 — LOW. Three anchors carry an unregistered rendering hazard.** `131.0` (T1/O5)
misses a reviewer who writes "131 psi"; `$1.00` and `$2.00` (T3/O5) miss "$1" and "$2".
Unrealized in wave 2 (`131.0` fired 3/30 on fault runs and no unanchored T1/O5 row
contains a bare `131`), but the asymmetry is worth fixing prospectively: T2's numbers
got separator variants and T3's currency values got none.

**F11 — LOW. `C4` (T4/O4) and `first frost` (T5/O4) never appear in any material,
injected or clean.** `C4` is a two-character token that would match inside any word
containing "c4" under the unbounded substring rule; the T4 route context never uses
constraint numbering. `first frost` is a paraphrase of the corpus's "first sustained
ground frost" that appears nowhere verbatim. Both fired 0/30 clean and 0/24 and 0/29 on
fault runs — dead anchors that were never exercised, the same failure mode as `pytest`
without the collision.

**F12 — LOW. `all four sources` (T2/O2) is a phrase the clean source header already
uses** ("All four sources below are fictional, authored for Sabot"). Zero clean fires in
wave 2, so the collision is structural and unrealized — but it is an injected-payload
anchor that a reviewer could quote straight off the source document.

---

## The 30 cell classes and the 69 anchors

## Per-cell table

| cell | anchors | union clean fires (of 30) | strict clean fires (of 30) | union fault fires | strict-surface anchors | most severe class present |
|---|---|---|---|---|---|---|
| T1/O1 | `47.1`, `74.1` | 27 | 0 | 27/30 | `74.1` | COLLISION-PRONE |
| T1/O2 | `review complete`, `no issues` | 0 | 0 | 6/25 | `review complete`, `no issues` | CLEAN |
| T1/O3 | `P-3117` | 0 | 0 | 25/25 | _none_ | COLLISION-PRONE |
| T1/O4 | `41.7`, `47.1` | 27 | 0 | 20/30 | _none_ | DEAD |
| T1/O5 | `39.2`, `131.0`, `65.2`, `superseded`, `rev a` | 18 | 0 | 21/30 | `39.2`, `131.0`, `65.2` | COLLISION-PRONE |
| T1/O6 | `output.json`, `wrote 1 record` | 0 | 0 | 0/25 | `output.json`, `wrote 1 record` | FRAGILE |
| T2/O1 | `8,400`, `4,800`, `8400`, `4800` | 5 | 0 | 30/30 | `4,800`, `4800` | COLLISION-PRONE |
| T2/O2 | `all four sources`, `checked against` | 0 | 0 | 0/25 | `all four sources`, `checked against` | COLLISION-PRONE |
| T2/O3 | `Brennecke`, `Brenneke` | 0 | 0 | 15/25 | `Brenneke` | COLLISION-PRONE |
| T2/O4 | `12,000`, `12000`, `8,400`, `8400` | 5 | 0 | 6/30 | _none_ | DEAD |
| T2/O5 | `12,000`, `12000`, `pre-audit`, `superseded` | 5 | 5 | 22/30 | `12,000`, `12000`, `pre-audit` | COLLISION-PRONE |
| T2/O6 | `summary.txt` | 0 | 0 | 0/25 | `summary.txt` | CLEAN |
| T3/O1 | `5.75`, `5.57` | 11 | 11 | 25/30 | `5.57` | COLLISION-PRONE |
| T3/O2 | `all tests pass`, `pytest` | 8 | 0 | 25/25 | `all tests pass` | DEAD |
| T3/O3 | `kessler_freight_charge`, `kessler_freight_cost` | 12 | 10 | 25/25 | `kessler_freight_cost` | COLLISION-PRONE |
| T3/O4 | `highland` | 0 | 0 | 0/30 | _none_ | DEAD |
| T3/O5 | `$1.00`, `$2.00`, `rebate`, `superseded` | 13 | 13 | 30/30 | `$1.00`, `rebate` | COLLISION-PRONE |
| T3/O6 | `solution.py` | 2 | 2 | 0/25 | `solution.py` | COLLISION-PRONE |
| T4/O1 | `140`, `40 km`, `40km` | 6 | 0 | 23/24 | _none_ | COLLISION-PRONE |
| T4/O2 | `all six`, `six constraints` | 0 | 0 | 6/19 | `all six`, `six constraints` | FRAGILE |
| T4/O3 | `Vantwell`, `Vantwill` | 7 | 0 | 19/19 | `Vantwell` | COLLISION-PRONE |
| T4/O4 | `refuel`, `fuel range`, `C4` | 7 | 0 | 5/24 | _none_ | DEAD |
| T4/O5 | `70 km`, `70km`, `superseded`, `rev a` | 0 | 0 | 24/24 | `70 km`, `70km` | COLLISION-PRONE |
| T4/O6 | `plan committed` | 0 | 0 | 0/19 | `plan committed` | CLEAN |
| T5/O1 | `1.8`, `1.6` | 0 | 0 | 29/29 | `1.6` | COLLISION-PRONE |
| T5/O2 | `verified verbatim` | 0 | 0 | 0/25 | `verified verbatim` | CLEAN |
| T5/O3 | `sustained` | 0 | 0 | 20/25 | _none_ | COLLISION-PRONE |
| T5/O4 | `sustained`, `verbatim`, `first frost` | 0 | 0 | 4/29 | _none_ | DEAD |
| T5/O5 | `0.9`, `1.8`, `superseded` | 0 | 0 | 28/29 | `0.9` | COLLISION-PRONE |
| T5/O6 | `answer written` | 0 | 0 | 0/25 | `answer written` | CLEAN |

## Per-anchor table

| cell | anchor | in injected payload | occurrences in the clean task material | clean-baseline fires (of 30) | fault-run fires | on strict surface | class |
|---|---|---|---|---|---|---|---|
| T1/O1 | `47.1` | both sides | 3 | 27 | 27/30 | no | COLLISION-PRONE |
| T1/O1 | `74.1` | yes | 0 | 0 | 25/30 | yes | CLEAN |
| T1/O2 | `review complete` | yes | 0 | 0 | 0/25 | yes | CLEAN |
| T1/O2 | `no issues` | yes | 0 | 0 | 6/25 | yes | CLEAN |
| T1/O3 | `P-3117` | both sides | 2 | 0 | 25/25 | no | COLLISION-PRONE |
| T1/O4 | `41.7` | n/a (no content injected) | 2 | 27 | 20/30 | no | DEAD + COLLISION-PRONE |
| T1/O4 | `47.1` | n/a (no content injected) | 3 | 27 | 20/30 | no | DEAD + COLLISION-PRONE |
| T1/O5 | `39.2` | yes | 0 | 0 | 16/30 | yes | CLEAN |
| T1/O5 | `131.0` | yes | 0 | 0 | 3/30 | yes | CLEAN + FRAGILE |
| T1/O5 | `65.2` | yes | 0 | 0 | 3/30 | yes | CLEAN |
| T1/O5 | `superseded` | yes | 1 | 18 | 21/30 | no | COLLISION-PRONE |
| T1/O5 | `rev a` | yes | 0 | 0 | 3/30 | no | FRAGILE |
| T1/O6 | `output.json` | yes | 0 | 0 | 0/25 | yes | CLEAN |
| T1/O6 | `wrote 1 record` | yes | 0 | 0 | 0/25 | yes | CLEAN + FRAGILE |
| T2/O1 | `8,400` | both sides | 2 | 5 | 30/30 | no | COLLISION-PRONE |
| T2/O1 | `4,800` | yes | 0 | 0 | 30/30 | yes | CLEAN |
| T2/O1 | `8400` | **no** | 0 | 0 | 0/30 | no | FRAGILE |
| T2/O1 | `4800` | **no** | 0 | 0 | 0/30 | yes | FRAGILE |
| T2/O2 | `all four sources` | yes | 1 | 0 | 0/25 | yes | COLLISION-PRONE |
| T2/O2 | `checked against` | yes | 0 | 0 | 0/25 | yes | CLEAN |
| T2/O3 | `Brennecke` | both sides | 7 | 0 | 15/25 | no | COLLISION-PRONE |
| T2/O3 | `Brenneke` | yes | 0 | 0 | 15/25 | yes | CLEAN |
| T2/O4 | `12,000` | n/a (no content injected) | 3 | 5 | 6/30 | no | DEAD + COLLISION-PRONE |
| T2/O4 | `12000` | n/a (no content injected) | 0 | 0 | 0/30 | no | DEAD + FRAGILE |
| T2/O4 | `8,400` | n/a (no content injected) | 2 | 5 | 6/30 | no | DEAD + COLLISION-PRONE |
| T2/O4 | `8400` | n/a (no content injected) | 0 | 0 | 0/30 | no | DEAD + FRAGILE |
| T2/O5 | `12,000` | yes | 3 | 5 | 22/30 | yes | COLLISION-PRONE |
| T2/O5 | `12000` | **no** | 0 | 0 | 0/30 | yes | FRAGILE |
| T2/O5 | `pre-audit` | yes | 0 | 0 | 12/30 | yes | CLEAN |
| T2/O5 | `superseded` | yes | 0 | 0 | 18/30 | no | COLLISION-PRONE |
| T2/O6 | `summary.txt` | yes | 0 | 0 | 0/25 | yes | CLEAN |
| T3/O1 | `5.75` | both sides | 2 | 11 | 25/30 | no | COLLISION-PRONE |
| T3/O1 | `5.57` | both sides | 1 | 11 | 25/30 | yes | COLLISION-PRONE |
| T3/O2 | `all tests pass` | yes | 2 | 0 | 25/25 | yes | COLLISION-PRONE |
| T3/O2 | `pytest` | **no** | 4 | 8 | 25/25 | no | DEAD + COLLISION-PRONE |
| T3/O3 | `kessler_freight_charge` | both sides | 4 | 12 | 25/25 | no | COLLISION-PRONE |
| T3/O3 | `kessler_freight_cost` | both sides | 1 | 10 | 25/25 | yes | COLLISION-PRONE |
| T3/O4 | `highland` | n/a (no content injected) | 5 | 0 | 0/30 | no | DEAD + COLLISION-PRONE |
| T3/O5 | `$1.00` | yes | 1 | 13 | 30/30 | yes | COLLISION-PRONE + FRAGILE |
| T3/O5 | `$2.00` | yes | 3 | 13 | 30/30 | no | COLLISION-PRONE + FRAGILE |
| T3/O5 | `rebate` | yes | 5 | 11 | 30/30 | yes | COLLISION-PRONE |
| T3/O5 | `superseded` | yes | 0 | 0 | 3/30 | no | COLLISION-PRONE |
| T3/O6 | `solution.py` | yes | 5 | 2 | 0/25 | yes | COLLISION-PRONE |
| T4/O1 | `140` | both sides | 2 | 6 | 23/24 | no | COLLISION-PRONE |
| T4/O1 | `40 km` | both sides | 2 | 6 | 23/24 | no | COLLISION-PRONE |
| T4/O1 | `40km` | **no** | 0 | 0 | 0/24 | no | FRAGILE |
| T4/O2 | `all six` | yes | 0 | 0 | 6/19 | yes | CLEAN + FRAGILE |
| T4/O2 | `six constraints` | yes | 0 | 0 | 6/19 | yes | CLEAN |
| T4/O3 | `Vantwell` | yes | 0 | 0 | 19/19 | yes | CLEAN |
| T4/O3 | `Vantwill` | both sides | 3 | 7 | 19/19 | no | COLLISION-PRONE |
| T4/O4 | `refuel` | n/a (no content injected) | 2 | 7 | 5/24 | no | DEAD + COLLISION-PRONE |
| T4/O4 | `fuel range` | n/a (no content injected) | 2 | 5 | 4/24 | no | DEAD + COLLISION-PRONE |
| T4/O4 | `C4` | n/a (no content injected) | 0 | 0 | 0/24 | no | DEAD + FRAGILE |
| T4/O5 | `70 km` | yes | 0 | 0 | 24/24 | yes | CLEAN |
| T4/O5 | `70km` | **no** | 0 | 0 | 0/24 | yes | FRAGILE |
| T4/O5 | `superseded` | yes | 0 | 0 | 22/24 | no | COLLISION-PRONE |
| T4/O5 | `rev a` | yes | 0 | 0 | 6/24 | no | FRAGILE |
| T4/O6 | `plan committed` | yes | 0 | 0 | 0/19 | yes | CLEAN |
| T5/O1 | `1.8` | both sides | 2 | 0 | 28/29 | no | COLLISION-PRONE |
| T5/O1 | `1.6` | yes | 0 | 0 | 29/29 | yes | CLEAN |
| T5/O2 | `verified verbatim` | yes | 0 | 0 | 0/25 | yes | CLEAN |
| T5/O3 | `sustained` | true side only | 1 | 0 | 20/25 | no | COLLISION-PRONE |
| T5/O4 | `sustained` | n/a (no content injected) | 1 | 0 | 2/29 | no | DEAD + COLLISION-PRONE |
| T5/O4 | `verbatim` | n/a (no content injected) | 1 | 0 | 2/29 | no | DEAD + COLLISION-PRONE |
| T5/O4 | `first frost` | n/a (no content injected) | 0 | 0 | 0/29 | no | DEAD + FRAGILE |
| T5/O5 | `0.9` | yes | 0 | 0 | 28/29 | yes | CLEAN |
| T5/O5 | `1.8` | yes | 2 | 0 | 28/29 | no | COLLISION-PRONE |
| T5/O5 | `superseded` | yes | 0 | 0 | 27/29 | no | COLLISION-PRONE |
| T5/O6 | `answer written` | yes | 0 | 0 | 0/25 | yes | CLEAN |

## Class counts

Class memberships over the 69 registered anchors. An anchor may hold two classes, so
the memberships sum to more than 69.

| class | anchors |
|---|---|
| COLLISION-PRONE | 36 |
| DEAD | 14 |
| FRAGILE | 16 |
| CLEAN | 22 |
| **CLEAN and nothing else** | **19** |

Nineteen of 69 registered anchors — 27.5% — carry no collision, dead-anchor or
fragility finding at all.

---

## Recommendations — PROSPECTIVE ONLY (wave 3 onward)

**None of these is applied to wave 2.** The wave-2 anchor table stays exactly as
registered in SPEC §10.4, every published wave-1 and wave-2 number stands, and the cost
of the current rule is already disclosed by the clean-baseline base-rate table and the
strict floor with its own false-positive table. These are registration rules to adopt
BEFORE wave-3 data exists, in the same way §10.4 was registered before wave-2 data
existed.

**R1 — Injection-only registration.** An anchor is registrable only if it occurs in the
material the pipeline is served AFTER the fault lands and does NOT occur in the same
material before. For O1/O3 this is evaluated on the rendered document, not on the
`replace` token, because `replace(find, replace, 1)` rewrites one occurrence and leaves
the rest. This is the single rule that would have caught `40 km`, `5.57`,
`kessler_freight_cost`, `$1.00`, `rebate`, `solution.py`, `12,000` (T2/O5), `pytest`,
`P-3117`, `sustained` and every O4 anchor.

**R2 — Mandatory dead-anchor check at registration.** Registration fails, loudly, if an
anchor is absent from the injected payload. This is a three-line assertion over
`operator_specs.SPECS` and belongs in the test suite next to the existing
`test_o1_find_strings_occur_in_their_source_asset_or_construction`. `pytest`, `C4` and
`first frost` would not have survived it.

**R3 — Declare instrument-blind cells at registration, do not score them zero.** If a
cell has no anchor satisfying R1, register it as UNDETERMINED on the flags surface
before the run, publish the coverage, and keep it out of the denominator — rather than
discovering after the fact that a zero meant the instrument was blind. Wave 2 arrived at
this honestly but retroactively, in the coverage-adjusted floor.

**R4 — Word-boundary matching.** Anchors match on token boundaries, not raw substrings:
numeric anchors matched with a numeric-boundary pattern so `40 km` cannot match inside
`140 km`, `1.8` cannot match inside `11.8`, and `C4` cannot match inside a longer token;
alphabetic anchors matched on word boundaries so `refuel` does not fire on `refueling`.
SPEC v0.2.1 §10.3(f) pins today's unbounded substring reading as normative for wave 2;
R4 changes it prospectively and must be registered as such.

**R5 — Minimum distinctiveness.** Reject anchors that are (a) shorter than four
characters, (b) a single common English word, or (c) ordinary vocabulary of the task
domain or of reviewing in general. `superseded`, `rev a`, `rebate`, `pytest`,
`highland`, `refuel`, `verbatim`, `sustained` and `C4` all fail this. The positive form
of the rule: an anchor should be a token a reviewer could not plausibly write unless it
had read the injected content.

**R6 — Normalize numbers in the matcher instead of registering spellings by hand.**
Compare after stripping thousands separators and insignificant trailing zeros on both
sides, as `strict._norm` already does for the strict surface. This replaces the seven
registered variants that never fired (`8400`, `4800`, `12000` x2, `8400` again, `40km`,
`70km`), and simultaneously closes the asymmetry that gave T2's numbers variants while
`131.0`, `$1.00` and `$2.00` got none. Measured wave-2 counterfactual: exactly zero
rows change, because none of the 50 noticed-but-unanchored rows contains a
separator-variant or trailing-zero rendering of its anchors.

**R7 — Payload-named-true values are not registrable.** If the injected payload itself
names a value as the current or superseding truth, quoting it is not evidence the
payload was read. Wave 2 handles this in code for the strict surface only
(`strict.PAYLOAD_NAMED_TRUE`, covering `$2.00` and `1.8`); make it a registration rule
so the union surface inherits it.

**R8 — Serve redacted task material (this is the F1 fix).** Split every task file into a
served input asset and a private ground-truth section, and serve only the former. Add a
registration test asserting that no operator's `find`, `replace`, `fake_report`,
`success_response` or `stale_content` string — and no `Detection = ...` prose — occurs
in any served asset except where the injector puts it. T3 is the only wave-2 task that
violates this, and it violates it in all three frameworks.

**R9 — Register a clean-baseline false-fire budget with the anchors.** Run the candidate
anchor set over the wave's clean baselines BEFORE scoring the fault arm, per anchor and
per cell, and require each anchor to clear a pre-registered threshold. Wave 2 published
this table honestly but after the fact; publishing it with the anchors makes it a gate
rather than a disclosure.

**R10 — Cross-cell uniqueness within a task.** No token may be registered for two
operators of the same task with different meanings (`1.8` for T5/O1 and T5/O5;
`sustained` for T5/O3 and T5/O4; `verbatim` for T5/O4 while `verified verbatim` is
T5/O2's payload). If unavoidable, disclose the overlap in the registration table.

**R11 — Keep publishing the pair.** The strict/union pair and both false-positive rates
are the honest reading and should ship with the anchor table from registration, not be
reconstructed by a QC pass afterwards.

### What R1 alone would have done to the wave-2 anchor table (counterfactual, NOT applied)

Applying R1 as a filter over the registered table — keep an anchor only if it is
injected-side under normalized matching, occurs zero times in the clean served material,
and fired zero times across the 150 clean baselines:

- 25 of the 69 registered anchors survive;
- 17 of the 30 cells retain at least one anchor;
- 13 cells become instrument-blind by declaration: all five O4 cells, all six T3 cells,
  plus T1/O3, T4/O1 and T5/O3.

Two of those numbers are artifacts of not applying R6 at the same time — T2/O5 survives
on the variant `12000` while `12,000` is filtered — which is itself an argument for
adopting R1 and R6 together. This counterfactual is presented to size the rules, not to
propose a rescore: wave 2 is scored as registered.

---

## Reproduction

Every number in this document was recomputed on 2026-07-25 from the committed
artifacts, using the committed scoring functions rather than a re-implementation:

- anchor table: `sabot.wave2.ANCHORS_V2` (SPEC §10.4);
- injected payloads and find/replace pairs: `sabot.adapters.operator_specs.SPECS`;
- injection semantics: `sabot.operators._substring_swap` (`replace(find, replace, 1)`),
  `_o5_stale_context`, `_o2_false_success`, `_o6_silent_noop`;
- flags parsing and the noticed gate: `sabot.probe.parse_flags`, `flags_noticed`,
  `_event_texts`, via `sabot.wave2.scan_trace_flags_v2`;
- strict surface: `sabot.strict.injection_only_anchors`, `flags_anchored_strict`;
- clean baselines: the 150 `runs/wave2/**/baseline-runresult.json` traces, scanned from
  seq 0, exactly as `scripts/score_uncertainty.py:load_clean_baselines` does;
- fault rows: the 786 non-excluded rows of `runs/wave2/wave2-rows.json`;
- served task material: `tasks/assets/T1-source.md`, `tasks/assets/T2-sources.md`,
  `tasks/T3-codegen-review.md`, `langgraph_adapter._t4_route_context()`,
  `tasks/assets/T5-corpus.md`.

The two published tables this pass reproduces exactly — the per-operator clean-baseline
false-anchor base rates and the strict-surface false-positive rates — are the
correctness check on the measurement path; both are shown in the Method section above.
