# Mutation Testing Receipts

Date: 2026-07-22
Tool: `mutmut>=3` (invoked as `python -m mutmut`, not on PATH by default — use a venv:
`python3 -m venv .venv && source .venv/bin/activate && python -m pip install -e '.[dev]'`)
Scope (`[tool.mutmut] paths_to_mutate` in `pyproject.toml`): `sabot/acts.py`,
`sabot/operators.py`, `sabot/score.py`. `sabot/trace.py` and `sabot/runner.py` are
explicitly out of scope for this phase (trace hardened separately; runner is a thin
seam covered by its own behavior tests).

## Initial run

| File | Killed | Survived | No-tests | Total |
|---|---|---|---|---|
| sabot/acts.py | 27 | 2 | 0 | 29 |
| sabot/operators.py | 97 | 18 | 0 | 115 |
| sabot/score.py | 38 | 4 | 0 | 42 |
| **Total** | **162** | **24** | **0** | **186** |

## Final run (after hardening)

| File | Killed | Survived | No-tests | Total |
|---|---|---|---|---|
| sabot/acts.py | 29 | 0 | 0 | 29 |
| sabot/operators.py | 115 | 0 | 0 | 115 |
| sabot/score.py | 42 | 0 | 0 | 42 |
| **Total** | **186** | **0** | **0** | **186** |

Honest denominator: 186 mutants generated across the three scoped files, all 186
killed. No mutants were suppressed, excluded, or marked equivalent — every survivor
was killed with a real behavioral test (exact `==`/`is` assertions on values, never a
substring-in check). Zero `DONE_WITH_CONCERNS` items; no dead code found and none
deleted.

## Survivors killed and what pinned them

**sabot/acts.py** (2 survivors)
- `hard_acts` default `since_seq` value (0 → 1): pinned by
  `test_default_since_seq_is_zero_includes_seq_zero_act`, a hard act at `seq=0`
  called via the default argument.
- `ValueError` message on unknown act (`f"unknown guardrail act: {act!r}"` → `None`):
  pinned by `test_unknown_act_error_message_names_the_bad_act`, exact `str(e)` match.

**sabot/operators.py** (18 survivors)
- `_substring_swap` fallback default for a missing field (`""` → `None` / omitted /
  `"XXXX"`, 3 mutants): pinned by
  `test_o1_field_absent_treated_as_empty_string_with_empty_find`, which uses an empty
  `find` against a payload missing the field entirely and checks the exact resulting
  dict — only the real `""` default lands cleanly with no leftover artifact.
  Note: this test also pins a real (if narrow) contract of the current code — a
  missing field is treated as empty text, and an empty `find` still "lands." It is
  documented behavior of the existing implementation, not new behavior invented for
  the test.
  Deep-copy shallow-copy mutant on the same function: pinned by
  `test_o1_deep_copies_nested_structures_not_shared_with_original` (mutate a nested
  structure on the returned payload, assert the original is untouched).
  `replace(..., 1)` count mutants (count dropped → replace-all; count changed to 2):
  pinned by `test_o1_replaces_only_the_first_occurrence` using a payload with the
  target substring occurring three times and asserting the exact resulting string.
- `_o5_stale_context`: the `or`/`and` guard mutant pinned by
  `test_o5_field_present_but_non_string_is_unverified` (non-string field value must
  short-circuit to unverified, not fall through to a `TypeError`); the five early-return
  mutants (`payload=None`, `verified=None`/`True`, missing kwarg) pinned by
  `test_o5_field_missing_returns_original_payload_unverified` (checks `r.verified is
  False` and `r.payload is payload` — the original object, not a copy); the
  deep/shallow-copy mutant pinned by
  `test_o5_deep_copies_nested_structures_not_shared_with_original`; the joiner-string
  literal mutant (`"\n"` → `"XX\nXX"`) pinned by
  `test_o5_joins_stale_content_with_exact_newline_separator`, an exact string `==`.
- `_field_replace` (backs O2/O6): the `payload=None` mutant on the missing-field path
  pinned by strengthening `test_o2_missing_field_unverified` to assert
  `r.payload is original`; the deep/shallow-copy mutant pinned by
  `test_o6_deep_copies_nested_structures_not_shared_with_original`.

**sabot/score.py** (4 survivors, all in `_excluded`)
- `reacted`/`recovered` forced to `None` or `True` on every excluded verdict: pinned
  by one test, `test_excluded_verdict_has_no_detection_reaction_or_recovery`, which
  compares the whole `CellVerdict` for equality against the exact expected dataclass
  instance — a single strong assertion that kills all four field-level mutants at
  once.

## Suite

`python -m pytest -q` — 41 passed (30 original + 11 added for this hardening pass).

## Concerns

None outstanding. No survivor was judged equivalent, so no `DONE_WITH_CONCERNS` /
Jeff-signed exemptions were needed.

---

# Phase 3: pure logic (Task 11)

Date: 2026-07-22
Scope added to `[tool.mutmut] source_paths` (Phase 2's three files stay in scope and
were re-verified at 186/186, unchanged): `sabot/checks.py`, `sabot/serde.py`,
`sabot/adapters/recorder.py`, `sabot/adapters/verdict.py`, `sabot/judge/rubric.py`.

## Config changes required (beyond adding the five files to `source_paths`)

- **`also_copy = ["sabot"]`**. mutmut only physically copies the exact files listed in
  `source_paths` into its sandboxed `mutants/` tree — it does not walk the rest of the
  package. Several of the Phase-3 files import sibling modules that are deliberately
  *not* mutated (`sabot/trace.py`, `sabot/runner.py`, `sabot/judge/runner.py`, the
  package `__init__.py` files); without `also_copy`, sandboxed pytest collection failed
  with `ModuleNotFoundError: No module named 'sabot.judge.runner'` (and would have hit
  the same wall for `sabot.trace` on collection of `test_score.py`/`test_acts.py`, just
  masked by `-x` stopping at the first failure). Copying the whole `sabot/` tree
  unmutated first is safe: `create_mutants()` runs *after* `copy_also_copy_files()` in
  mutmut's own `_run()`, so it overwrites exactly the `source_paths` files with their
  mutated versions — nothing here dilutes what actually gets mutated. (This gap
  predates Phase 3; Phase 2's narrower 3-file scope happened not to need any of these
  sibling imports transitively required at collection time in a way that surfaced it.)
- **`pytest_add_cli_args_test_selection = ["--ignore=tests/test_venvs.py"]`**.
  `tests/test_venvs.py` resolves its root via `Path(__file__).resolve().parent.parent`,
  which breaks once mutmut physically copies the test file into `mutants/tests/` (root
  becomes `mutants/` instead of the real repo root, so the `.venv-*` framework venvs it
  checks for "don't exist" there and the baseline test run fails before any mutant is
  even generated). It exercises no `sabot/*.py` source line, so excluding it from
  mutmut's own internal test run has zero effect on mutation coverage — it still runs
  normally under a plain `pytest -q` from the repo root (verified: 1 passed).

## Timeout

`[tool.mutmut] timeout_multiplier` (default 15.0) / `timeout_constant` (default 1.0)
were evaluated and left at their defaults — sane for this suite. mutmut sizes each
mutant's wall-clock budget off the *measured baseline suite runtime*
(`(baseline + timeout_constant) * timeout_multiplier`), and the baseline (full offline
suite, `judge_live` still deselected via the copied `pyproject.toml` addopts) runs in
~2.4–3.1s even with `check_t3`'s pytest-subprocess tests included, giving each mutant
~35–50s before mutmut kills it as a timeout. That budget mattered: four of the
hardening tests added below (`parse_judge_output`'s brace-retry loop) are constructed
so that four specific mutants degrade into a genuine infinite loop rather than a wrong
answer — mutmut's own timeout is what turns that into a caught mutant (`timeout`
status) instead of a hang. No override was needed; had the baseline been slower (e.g.
if a framework-venv test leaked into the baseline), `timeout_multiplier` would have
needed lowering to keep the run inside the ~45-minute budget.

## Runtime

Single full pass, all 8 files, no splitting needed:
`.venv/bin/python -m mutmut run` — 637 mutants total, **17.9s wall clock**
(`71.55s user 8.30s system 445% cpu 17.929 total`; mutmut parallelizes across
`os.cpu_count()` workers by default, which is also why the four timeout mutants above
didn't dominate wall time — they ran concurrently with everything else).

## Initial run (5 new files)

| File | Killed | Survived | No-tests | Total |
|---|---|---|---|---|
| sabot/checks.py | 133 | 30 | 0 | 163 |
| sabot/serde.py | 79 | 7 | 0 | 86 |
| sabot/adapters/recorder.py | 64 | 20 | 8 | 92 |
| sabot/adapters/verdict.py | 11 | 1 | 0 | 12 |
| sabot/judge/rubric.py | 71 | 27 | 0 | 98 |
| **Phase 3 subtotal** | **358** | **85** | **8** | **451** |
| Phase 2 (re-verified, unchanged) | 186 | 0 | 0 | 186 |
| **Grand total** | **544** | **85** | **8** | **637** |

## Final run (after hardening)

| File | Killed | Survived | Timeout | No-tests | Total |
|---|---|---|---|---|---|
| sabot/checks.py | 163 | 0 | 0 | 0 | 163 |
| sabot/serde.py | 86 | 0 | 0 | 0 | 86 |
| sabot/adapters/recorder.py | 92 | 0 | 0 | 0 | 92 |
| sabot/adapters/verdict.py | 12 | 0 | 0 | 0 | 12 |
| sabot/judge/rubric.py | 92 | **2** | **4** | 0 | 98 |
| Phase 2 (re-verified, unchanged) | 186 | 0 | 0 | 0 | 186 |
| **Grand total** | **631** | **2** | **4** | **0** | **637** |

**Honest denominator**: 637 mutants generated across the eight scoped files. 631
killed outright. 4 more are caught (not survived) but land in mutmut's `timeout`
bucket rather than `killed` — see "Four timeout-catches" below; they are genuine
detections, not gaps. 2 are judged equivalent and left as `survived` under the
STOP-GATE (see "Two flagged equivalents" below) — nobody wrote an exemption or deleted
code for them; that call is Jeff's, not the builder's.

## What pinned the Phase-3 survivors

**sabot/checks.py** (30 survivors, e.g. `"assets"` → `"ASSETS"`, `"T1-golden.json"` →
`"t1-golden.json"`): macOS/APFS is case-insensitive by default, so these path-casing
mutants are byte-identical on disk and invisible to a test that just calls `check_t1`
and checks the boolean result. Killed by spying on the real I/O call
(`pathlib.Path.read_text`, `subprocess.run`, `importlib.util.spec_from_file_location`)
and asserting the *exact* path/name argument passed — `test_check_t1_reads_golden_json_from_exact_path`,
`test_check_t2_reads_claims_json_from_exact_path`,
`test_check_t3_shells_pytest_with_exact_suite_path_and_kwargs`,
`test_check_t4_uses_exact_module_name_and_asset_path`,
`test_check_t5_reads_corpus_and_answerkey_from_exact_paths`. The `check_t3` spy also
kills the `subprocess.run` kwarg mutants (`capture_output`/`text`/`timeout` flipped to
`None`/`False`/a different int, or omitted) that are invisible to `check_t3`'s own
return value (it only reads `proc.returncode`) but are real, observable differences in
what the harness actually shells out — pinned via one exact `kwargs` comparison rather
than several loose ones. Two real logic survivors: `check_t2`'s exemption-keyword
`.lower()` → `.upper()` mutant, killed by
`test_t2_forbidden_substring_paired_with_exemption_keyword_in_same_sentence_is_exempted`
(a sentence carrying both the forbidden figure and a retraction keyword, which only the
real case-insensitive match exempts); and `check_t5`'s `or`/`and` boundary-check
mutants plus its `return False`→`return True` mutant, killed by three targeted cases
(empty-but-valid-type citations list, non-string answer with otherwise-valid
citations, and a non-list `citations` value).

**sabot/serde.py** (7 survivors): all three `json.dumps(..., sort_keys=True)` calls
had their `sort_keys` argument mutated to `None`/omitted/`False`. Since the source
dicts' insertion order is deliberately *not* alphabetical, a plain string-equality test
against an independently-recomputed `sort_keys=True` expectation
(`test_run_result_to_json_keys_are_sorted_alphabetically`,
`test_cell_verdict_to_json_keys_are_sorted_alphabetically`) kills all three variants of
each call at once. `cell_verdict_from_json`'s `excluded=d["excluded"]` → `excluded=None`
mutant survived because the existing round-trip test happened to use `excluded=None`
already; `test_cell_verdict_from_json_preserves_non_none_excluded` round-trips a
non-`None` value instead.

**sabot/adapters/recorder.py** (28: 20 survived + 8 no-tests, all now killed): the
`verdict()` method had zero test coverage at all (all 8 of its mutants were "no
tests") — `test_verdict_emits_kind_agent_payload_exact` covers it, and also happens to
catch the `kind="verdict"`→`"VERDICT"`/`"XXverdictXX"` mutants for free via
`Event.__post_init__`'s own `kind` validation. The `__init__` mutants (each
constructor arg forwarded to `Trace` swapped for `None`) survived because no existing
test ever read the trace's own metadata fields back —
`test_init_stores_all_constructor_fields_on_trace` does. The `_emit`/`agent_msg`/
`tool_call`/`guardrail`/`inject` mutants (agent swapped for `None`, payload keys
renamed/cased, `tool_call`'s `injected` default flipped to `True`) survived because
existing tests checked `payload` dict contents but not the `Event.agent` field, and
never called `tool_call` without an explicit `injected=` to exercise the default. New
tests assert on the *whole* `Event` via dataclass `==` (exact field-for-field) instead
of picking individual dict keys, which kills several mutants per test.

**sabot/adapters/verdict.py** (1 survivor): `text or ""` → `text or "XXXX"`. Both
fallback strings fail to match the `VERDICT:` regex, so the mutant is invisible from
`parse_verdict`'s return value for every possible falsy `text` — pinned instead by
spying on `_TOKEN.search` (a fake regex object substituted via monkeypatch) and
asserting the exact string it was called with is `""`, the same technique used for the
checks.py path mutants.

**sabot/judge/rubric.py** (98 total; 92 killed, 4 timeout, 2 flagged equivalent):
- `_render_event`'s `sort_keys=True` mutants: same technique as serde.py, a payload
  whose insertion order isn't already alphabetical.
- `build_rubric`'s default `prompt_variant` (0→1): call without the kwarg and diff
  against an explicit `prompt_variant=0` call.
- `build_rubric`'s `ValueError` message reduced to `None`: exact `str(exc.value)`
  match.
- `build_rubric`'s join separator (`"\n"`→`"XX\nXX"`) and empty-transcript literal
  (`"(no events)"`→`"XX(no events)XX"`/`"(NO EVENTS)"`): the first pass at the
  empty-transcript test used `"(no events)" in prompt`, which is exactly the
  substring-presence trap the Phase-2 receipts warn against — `"(no events)"` is
  itself a substring of the mutant's `"XX(no events)XX"`, so it silently passed under
  both. Fixed to assert the exact delimited substring
  `f"{_TRANSCRIPT_HEADER}\n(no events)\n\n{_NOTE_HEADER}"`, which only the real literal
  satisfies.
- `parse_judge_output`'s JSON-decode error messages (`None`-ed out, or the `[:200]`
  truncation slice bumped to `[:201]`): exact `str(exc.value)` matches, one test using
  a 250-char no-brace input specifically to make the truncation boundary observable.
- `parse_judge_output`'s brace-retry loop (`idx = 0` → `idx = 1`; `text.find("{", idx)`
  → `text.rfind(...)`; the post-failure `idx += 1` → `idx = 1`/`idx -= 1`/`idx += 2`):
  killed by three constructed inputs exercising the retry path directly — JSON that
  starts exactly at index 0 with unparseable trailing text (kills the `idx=1` initial
  value), a `{` embedded inside a string value that must not be mistaken for the
  object's real start (kills `find`→`rfind`), and a false leading `{{` that must be
  skipped by exactly one position on retry (kills the `+=1`→`=1`/`-=1`/`+=2` variants).
  `cohens_kappa`'s two `ValueError` messages: exact `str(exc.value)` matches.

### Four timeout-catches (not survived, not a concern)

`sabot.judge.rubric.x_parse_judge_output__mutmut_11/13/27` (the post-failure retry
index reset to a fixed value instead of advancing) and `_mutmut_28` (`idx += 1` →
`idx -= 1`) all degrade, under the brace-retry-loop test above, into a genuine infinite
loop: the mutated `idx` gets reset back onto the same already-failing brace position
every iteration instead of moving past it. mutmut's own timeout mechanism catches
this (`(baseline + 1) * 15 ≈ 35–50s` per mutant) and reports `timeout`, not `killed`,
but it is real, correct detection — an actual infinite-loop bug in judge-output
parsing is arguably a more serious defect than a wrong return value, since it would
hang the real soft-tier judge on malformed model output. Verified this doesn't add
meaningful wall time: mutmut runs mutants in parallel across CPU cores, so these four
overlapped with the rest of the 637-mutant run rather than serializing (full run still
17.9s).

### Two flagged equivalents (STOP-GATE, unresolved — Jeff's call)

Per the Task 11 stop-gate: no test was written to force a "kill," and no code was
deleted, for these two `parse_judge_output` survivors. Both are provably unobservable
from any test, given the function's own control flow — not an environment artifact
like the checks.py case-insensitivity issue, but dead-by-construction:

1. **`sabot.judge.rubric.x_parse_judge_output__mutmut_2`** — `obj = None` → `obj = ""`.
   ```diff
       text = text.strip()
   -   obj = None
   +   obj = ""
       try:
           obj = json.loads(text)
       except json.JSONDecodeError:
           ...
   ```
   `obj` is unconditionally reassigned before it is ever read on every reachable path:
   either `json.loads(text)` succeeds and overwrites it directly, or it fails and the
   `except` branch either raises (before the initial value is ever read) or succeeds
   via `raw_decode` (which also overwrites it) before `break`ing out to the code that
   reads `obj`. There is no path where the initial value survives to be observed.

2. **`sabot.judge.rubric.x_parse_judge_output__mutmut_6`** — `idx = 0` → `idx = None`
   (the initialization *before* the retry loop, not the in-loop retry mutants above).
   ```diff
       decoder = json.JSONDecoder()
   -   idx = 0
   +   idx = None
       while True:
           idx = text.find("{", idx)
   ```
   Verified empirically (`'xx{{yy'.find('{', None) == 'xx{{yy'.find('{', 0) == 2`):
   CPython's `str.find` treats a `None` start identically to `0`/omitted. The very
   next line unconditionally reassigns `idx` via `text.find("{", idx)` before it is
   used for anything else, so `0` vs. `None` as the seed value is behaviorally
   identical for every possible input.

If either read as dead code worth simplifying (e.g. dropping the `obj = None` /
`idx = 0` pre-initializations entirely and restructuring the control flow so a linter
doesn't need them), that's a real code change and Jeff's/the maintainer's call, not
something to make unilaterally under a "make mutation testing pass" mandate.

## Suite

`.venv/bin/python -m pytest -q` (core venv) — 107 passed, 6 skipped (framework-adapter
tests gated by `pytest.importorskip`), 2 deselected (`judge_live`). 32 new tests added
this pass (75 → 107).
`.venv-langgraph/bin/python -m pytest tests/test_langgraph_adapter.py
tests/test_probes_langgraph.py -q` — 34 passed (framework-venv spot check).

## Concerns

Two flagged equivalents above, awaiting Jeff's sign-off (accept as `DONE_WITH_CONCERNS`
equivalent, or approve a follow-up simplification of `parse_judge_output`'s
pre-loop initializers). Everything else in scope — Phase 2's three files and all five
Phase 3 files — is at zero unexplained survivors.

## Resolution of the two flagged equivalents (2026-07-22, same day)

Resolved via the plan's pre-approved "deletion preferred" path (Task 11 STOP-gate:
"Jeff signs or the dead code is deleted (deletion preferred)"): `parse_judge_output`'s
dead pre-initializations (`obj = None`, `idx = 0`) were removed and the fallback scan
restructured (`idx = text.find("{")` seed; retry `idx = text.find("{", idx + 1)`;
`idx == -1` checked after the loop). The two equivalent-mutant sites no longer exist.
The restructure surfaced one NEW killable mutant (`find` -> `rfind` in the retry scan),
killed by `test_parse_retry_scan_moves_left_to_right_not_to_the_last_brace` (a dangling
`{` after the valid object separates the behaviors).

Final re-run over the full 8-file scope: 639 mutants generated on the restructured code,
**0 survived, 0 equivalents outstanding** (3 timeouts = caught: those mutants hang the
retry loop and mutmut's timeout kills them; counted as detected, consistent with the
initial pass's convention). Suite after resolution: 108 passed, 6 skipped, 2 deselected.

---

# Phase 4: matrix / notes / scoreboard (Task 6)

Date: 2026-07-22
Scope added to `[tool.mutmut] source_paths` (Phases 2-3's eight files stay in scope and
were re-verified unchanged): `sabot/matrix.py`, `sabot/judge/notes.py`,
`sabot/scoreboard.py`. These are the three new pure modules of Phase 4 — matrix.py's
spend model gates the $500 hard cap and scoreboard.py computes the numbers that
publish, so this task's bar is 0 survivors across exactly these three files.

## Config changes required (beyond adding the three files to `source_paths`)

- **`also_copy = ["sabot", "scripts"]`**. `tests/test_run_matrix.py` and
  `tests/test_run_judge.py` (indirect coverage of `matrix.py`) load
  `scripts/run_matrix.py` / `scripts/run_judge.py` via `importlib.util`, resolving the
  repo root as `Path(__file__).resolve().parent.parent`. Once mutmut copies the test
  file into `mutants/tests/`, that root resolves to `mutants/`, and the driver scripts
  must exist there too or collection fails with `FileNotFoundError: .../mutants/scripts/
  run_judge.py`. Neither script is in `source_paths`, so copying them unmutated has
  zero effect on mutation coverage — it only makes the two indirect-coverage suites
  collectible in the sandbox. Same category of gap as Phase 3's `also_copy = ["sabot"]`
  (mutmut only physically copies exactly the files in `source_paths`, not the rest of
  the repo a sandboxed collection needs).

## Runtime

`.venv/bin/python -m mutmut run` — 959 mutants total (639 carried over from Phases 2-3
plus 320 new), ~19.3s wall clock (415% cpu, parallelized across cores).

## Initial run (3 new modules)

| File | Killed | Survived | Timeout | No-tests | Total |
|---|---|---|---|---|---|
| sabot/matrix.py | 13 | 0 | 0 | 0 | 13 |
| sabot/judge/notes.py | 36 | 11 | 0 | 0 | 47 |
| sabot/scoreboard.py | 173 | 87 | 0 | 0 | 260 |
| **Phase 4 subtotal** | **222** | **98** | **0** | **0** | **320** |
| Phases 2-3 (re-verified, unchanged) | 636 | 0 | 3 | 0 | 639 |
| **Grand total** | **858** | **98** | **3** | **0** | **959** |

`matrix.py` needed zero hardening — its existing suite (`test_matrix.py` +
`test_run_matrix.py`) already killed every mutant on the first pass.

## Final run (after hardening)

| File | Killed | Survived | Timeout | No-tests | Total |
|---|---|---|---|---|---|
| sabot/matrix.py | 13 | 0 | 0 | 0 | 13 |
| sabot/judge/notes.py | 47 | 0 | 0 | 0 | 47 |
| sabot/scoreboard.py | 260 | 0 | 0 | 0 | 260 |
| Phases 2-3 (re-verified, unchanged) | 636 | 0 | 3 | 0 | 639 |
| **Grand total** | **956** | **0** | **3** | **0** | **959** |

**Honest denominator**: 959 mutants generated across the eleven scoped files. 956
killed outright. 3 land in mutmut's `timeout` bucket, unchanged from Phase 3 —
`sabot.judge.rubric.x_parse_judge_output__mutmut_20/22/25`, the already-documented
genuine infinite-loop catches in the brace-retry scan (out of this task's scope, not
regressed). 0 survived. No mutant was suppressed, excluded, or marked equivalent for
the three new modules — every survivor was killed with a real behavioral test (exact
`==` assertions on values and, for `render_markdown`, the entire return string — never
a substring-in check).

## What pinned the Phase-4 survivors

**sabot/judge/notes.py** (11 survivors, all in `ground_truth_note`):
- Two `KeyError(...)` messages reduced to `KeyError(None)` (missing task file; missing
  ground-truth section): pinned by
  `test_unknown_task_error_message_names_the_task_and_dir` and
  `test_missing_ground_truth_section_error_names_the_matched_file`, exact
  `exc.value.args[0]` matches.
- `matches[0].name` → `matches[1].name` in the missing-section error message: no
  existing test used a `tasks_dir` with two files sharing the same `{task_id}-*.md`
  prefix, so the mutant's `matches[1]` never had a chance to disagree with `matches[0]`.
  Pinned by
  `test_missing_section_error_names_first_sorted_match_when_multiple_files_share_prefix`,
  two synthetic files where only the alphabetically-first one's name is correct.
- `text.split(_SECTION, 1)[1]` mutated three ways (no `maxsplit` i.e. split-all,
  `rsplit` from the right, `maxsplit=2`): all three are invisible when `_SECTION`
  appears exactly once in the source text (the only case the real task files and prior
  tests exercised). Pinned by `test_split_uses_maxsplit_one_not_greedy_or_reverse`, a
  synthetic file with a SECOND literal occurrence of `_SECTION` embedded inline
  mid-bullet (not at a line start, so it can't be mistaken for a real heading) — the
  real code's `maxsplit=1` keeps that embedded text verbatim in the extracted note;
  split-all truncates before it, and `rsplit` drops the O1 bullet entirely.
- The `next_heading` truncation logic mutated four ways (`None`-ed out, the
  `re.MULTILINE` flag dropped, the `r"^## "` pattern literal swapped, and the
  truncation assignment itself `None`-ed out): none of the prior tests had a task file
  with a genuine trailing `## ` heading after the target operator's bullet, so nothing
  ever depended on truncation firing. Pinned by
  `test_truncates_at_next_heading_line_after_the_section`, a synthetic file with a
  decoy `## Next Heading` section containing a duplicate O1 bullet marked `DROPPED` —
  the real code must exclude it.
- The final `KeyError` message for an unknown operator ID, reduced to `KeyError(None)`:
  pinned by `test_unknown_operator_error_message_names_task_and_operator`, exact
  `exc.value.args[0]` match (the pre-existing
  `test_unknown_task_or_operator_raises_keyerror` only checked the exception type,
  never the message).

**sabot/scoreboard.py** (87 survivors: 6 real logic + 81 in `render_markdown`):
- `_row`'s `rate()` closure's zero-denominator fallback (`0.0` → `1.0`): every prior
  test's groups had at least one valid (non-excluded) record. Pinned by
  `test_row_rate_denominator_zero_defaults_to_zero_not_one`, a group where every
  record is excluded (`injected=2, valid=0`), asserting all five rates are exactly
  `0.0`.
- `recovery_without_detection`'s `not _noticed(r)` → `_noticed(r)` (dropped negation):
  the existing `test_row_rates_and_override_gap` fixture happened to have one
  noticed-and-recovered case and one unnoticed-and-recovered case whose contributions
  to the rate summed to the same value under both the real predicate and its
  negation-dropped mutant (0.25 either way) — a coincidental cancellation, not a real
  kill. Pinned by `test_recovery_without_detection_excludes_noticed_recoveries`, a
  single noticed-and-recovered record where the two predicates diverge (`0.0` real vs
  `1.0` mutant).
- `aggregate`'s per-group filter (`r.framework == fw and r.config == cfg` → `or`):
  every prior aggregate test used records where framework and config were both either
  matching or both non-matching for a given group, so `and`/`or` never disagreed.
  Pinned by `test_aggregate_groups_records_by_framework_and_config_exactly`, three
  records that pairwise share exactly one of the two fields with the target group —
  the `or` mutant would pull in the mismatched records, inflating `injected` from 1 to
  3.
- `_row(fw, cfg, recs)` call-site args swapped to `_row(None, cfg, recs)` /
  `_row(fw, None, recs)`: no prior test read the returned row's own `"framework"` /
  `"config"` dict keys (only aggregate-level fields like counts and rates). Pinned by
  `test_row_dict_carries_the_actual_framework_and_config_labels`.
- `_pct`'s `100 * x` → `101 * x`: pinned by
  `test_render_markdown_percent_formatting_is_exact_hundred_multiplier` (a clean
  `sabot_score == 1.0` case where `100.0%` vs `101.0%` are unambiguous).
- `render_markdown`'s 81 remaining mutants (literal headings, table separators, the
  `_pct`/kappa/median format strings, the judge-exclusion and appendix line templates,
  the `"\n".join` structure itself): the pre-existing test only checked a handful of
  substrings (`"Sabot Score" in md`, `"LOW-CONFIDENCE" in md`, etc.) — exactly the
  substring-in trap the Phase-2/3 receipts warn against, since nearly any literal-text
  mutation still contains those substrings somewhere in the ~35-line output. Pinned by
  three new tests asserting the **entire** `render_markdown` return value with exact
  `==` against a hand-verified expected string, each covering a different branch
  combination: `test_render_markdown_full_featured_scenario_exact` (3 rows, `kappa`
  present with a real `.3f` value, `judge_exclusions` present, exclusion appendix
  present, `median_hard` present), `test_render_markdown_minimal_scenario_exact`
  (single row, `kappa=None`, no exclusions, `median_hard=None`), and
  `test_render_markdown_kappa_none_value_and_low_confidence_flag_exact` (targets the
  `kappa["kappa"] is None` → `"N/A"` branch and the `low_confidence` flag text
  specifically). Between the three, every literal string and every conditional branch
  in the function is pinned by an exact full-string comparison.

## Suite

`.venv/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py` — 145 passed, 6
skipped, 2 deselected. 14 new tests added this pass (131 → 145; 6 in
`test_judge_notes.py`, 8 in `test_scoreboard.py`).
`.venv/bin/python -m pytest tests/ -q` (including `test_venvs.py`) — 147 passed, 6
skipped, 2 deselected.

## Concerns

None outstanding. No survivor was judged equivalent for the three new modules; no
source module was modified and no test was weakened or deleted to dodge a mutant.
Phases 2-3's eight files and their documented 3-timeout / 2-resolved-equivalent history
are unchanged.

# Wave 2: sabot/wave2.py + recorder seam (v0.2.0 build)

Date: 2026-07-23
Scope added: `sabot/wave2.py` (anchors, FLAGS scan, carve-out, T2 structural check,
O4 landing probe). The recorder's additive `model_id` kwarg regenerated
`recorder.py` mutants.

## Initial run

1,178 mutants total (959 carried + 219 new): 1,147 killed, 28 survived
(25 in wave2.py: scan_trace_flags_v2 9, o4_landed 11, t2_structural_check 5;
3 in recorder.agent_msg's new model_id branch — untested in the base venv because
the adapter suites importorskip there), 3 timeout (the documented rubric
infinite-loop catches, unchanged).

## Hardening (12 tests appended to tests/test_wave2.py)

Survivor classes killed by construction: dict-default variants (missing
events/seq/payload keys), continue->break order dependence (multi-event fixtures),
the seq at-boundary `<` vs `<=` rule (flag at exactly injection_seq counts),
o4_landed's default-injection and malformed-event paths, exact reason-string and
exact-word-limit pins for t2_structural_check, and exact payload-dict equality for
recorder.agent_msg with/without model_id.

## Final run

1,178 mutants: **1,175 killed, 0 survivors**, 3 timeout (rubric, pre-existing,
documented). Wave-2 pure logic enters the paid run mutation-clean.
