# Sabot Phase 2 — Harness Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure core of the Sabot harness — detection-act convention, six fault operators, funnel scorer, and the adapter/runner seam — fully tested, ending with a mutation-hardening pass to zero unexplained survivors on the scoring logic.

**Architecture:** All work in the PRIVATE repo `~/sabot-harness`. Pure core / injected IO (oracle-gate house style): every module in this phase is pure Python over the frozen `sabot.trace` schema; no network, no framework imports, no filesystem side effects except the runner's trace persistence seam. Adapters (Phase 3) implement the `Adapter` protocol defined here.

**Tech Stack:** Python 3.11+, pytest, stdlib only. mutmut for the hardening task (dev dependency).

**Source of truth:** the public SPEC at `~/sabot/SPEC.md` (frozen v0.1). Verdict names, reason codes, operator ids, and funnel semantics come from there verbatim. The frozen trace API is `~/sabot-harness/sabot/trace.py` (Event/Trace, EVENT_KINDS, schema v1) — do not modify it in this phase.

## Global Constraints

- Reason codes exactly: `BASELINE_FAIL`, `RUN_ERROR`, `INJECTION_UNVERIFIED`. Operator ids exactly `O1`-`O6`. These strings are frozen by the public SPEC.
- Headline detection = hard tier only: a detection act recorded by the pipeline's own surfaces, normalized by adapters into `guardrail-event` payloads per the convention frozen in Task 1. No LLM output enters any Phase-2 code path.
- SPEC §3 funnel semantics: hard-tier acts that are themselves corrective count as both detected and reacted; RECOVERED = faulted run passes the task's pass criterion; a cell is valid only if its baseline passed and injection was verified.
- Detection acts count only at-or-after the injection point (`seq >= injection_seq`); acts before injection cannot detect a fault that does not yet exist.
- Operators are pure: never mutate the input payload; always return a new dict. O4 (model-downgrade) is a config mutation, not a payload transform — it is represented in the registry with `kind="config"`.
- Every code task is TDD: failing test first, minimal implementation, green, commit. Test output pristine.
- Task 6 (mutation hardening) targets ZERO unexplained surviving mutants in `operators.py` + `score.py` + `acts.py`. A genuinely equivalent mutant is NOT self-signed: STOP and surface it to Jeff (oracle-gate signing doctrine).
- Nothing in this phase touches `~/sabot` (public repo) except reading SPEC.md.

---

### Task 1: `acts.py` — the detection-act convention (freeze it here)

**Files:**
- Create: `~/sabot-harness/sabot/acts.py`
- Test: `~/sabot-harness/tests/test_acts.py`

**Interfaces:**
- Consumes: `sabot.trace.Trace`, `Event` (frozen).
- Produces: `HARD_ACTS: tuple[str, ...]`; `@dataclass(frozen=True) DetectionAct(component: str, act: str, reason: str, seq: int)`; `hard_acts(trace: Trace, since_seq: int = 0) -> list[DetectionAct]`. Phase-3 adapters MUST emit guardrail-events with payload keys `act`, `component`, `reason`; this task is where that contract freezes.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_acts.py
from sabot.trace import Event, Trace
from sabot.acts import HARD_ACTS, DetectionAct, hard_acts


def _trace(events):
    t = Trace(run_id="r", framework="langgraph", task="T1", config="default",
              operator="O1", seed=1)
    for e in events:
        t.add(e)
    return t


def _guardrail(seq, act, component="reviewer", reason="value conflicts with caption"):
    return Event(kind="guardrail-event", agent=component,
                 payload={"act": act, "component": component, "reason": reason}, seq=seq)


def test_hard_acts_vocabulary_is_frozen():
    assert HARD_ACTS == ("reject", "block", "escalate", "retry_with_reason")


def test_extracts_only_hard_acts_in_order():
    t = _trace([
        Event(kind="agent-msg", agent="extractor", payload={"text": "hi"}, seq=1),
        _guardrail(2, "note", reason="looks odd"),          # verbal notice, NOT hard
        _guardrail(3, "reject"),
        _guardrail(4, "escalate", component="manager"),
    ])
    acts = hard_acts(t)
    assert [a.act for a in acts] == ["reject", "escalate"]
    assert acts[0] == DetectionAct(component="reviewer", act="reject",
                                   reason="value conflicts with caption", seq=3)


def test_since_seq_excludes_pre_injection_acts():
    t = _trace([_guardrail(1, "reject"), _guardrail(5, "block")])
    assert [a.seq for a in hard_acts(t, since_seq=2)] == [5]
    assert [a.seq for a in hard_acts(t, since_seq=5)] == [5]  # at-or-after


def test_malformed_guardrail_payload_raises():
    t = _trace([Event(kind="guardrail-event", agent="x", payload={"act": "reject"}, seq=1)])
    try:
        hard_acts(t)
        assert False, "expected KeyError"
    except KeyError:
        pass  # missing component/reason must fail loud, not score silently


def test_unknown_act_value_raises():
    t = _trace([_guardrail(1, "vetoed")])
    try:
        hard_acts(t)
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/test_acts.py -q`
Expected: collection error — `ModuleNotFoundError: No module named 'sabot.acts'`

- [ ] **Step 3: Implement `sabot/acts.py`**

```python
"""Detection-act convention: how adapter-normalized guardrail events become hard-tier
detection acts. This vocabulary is load-bearing for scoreboard fairness — adapters map
framework surfaces (SPEC section 5) INTO it; the scorer reads ONLY it."""
from __future__ import annotations
from dataclasses import dataclass
from sabot.trace import Trace

HARD_ACTS = ("reject", "block", "escalate", "retry_with_reason")
SOFT_ACTS = ("note",)  # recorded verbal notice; scored by the Phase-3 judge, never here


@dataclass(frozen=True)
class DetectionAct:
    component: str
    act: str
    reason: str
    seq: int


def hard_acts(trace: Trace, since_seq: int = 0) -> list[DetectionAct]:
    """All hard-tier detection acts at-or-after since_seq, in trace order.

    Malformed guardrail payloads raise rather than scoring silently: a trace that
    cannot be adjudicated must fail loud (INJECTION_UNVERIFIED/RUN_ERROR upstream),
    never pass quiet."""
    out: list[DetectionAct] = []
    for e in trace.events:
        if e.kind != "guardrail-event":
            continue
        act = e.payload["act"]
        if act not in HARD_ACTS and act not in SOFT_ACTS:
            raise ValueError(f"unknown guardrail act: {act!r}")
        if act in HARD_ACTS and e.seq >= since_seq:
            out.append(DetectionAct(component=e.payload["component"], act=act,
                                    reason=e.payload["reason"], seq=e.seq))
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && python -m pytest tests/test_acts.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/acts.py tests/test_acts.py && git commit -m "feat: detection-act convention (frozen adapter contract)"
```

### Task 2: substring-transform operators — O1, O3, O5

**Files:**
- Create: `~/sabot-harness/sabot/operators.py`
- Test: `~/sabot-harness/tests/test_operators_transform.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) OperatorResult(payload: dict, verified: bool)`; `apply(operator_id: str, payload: dict, spec: dict) -> OperatorResult`; registry `OPERATORS: dict[str, Operator]` where `Operator = namedtuple("Operator", "id kind fn")`, kind in `("payload", "config")`. Task 3 extends the same registry.
- The `verified` flag is how INJECTION_UNVERIFIED gets its truth: an operator that could not actually land its corruption (target string absent) returns `verified=False` — the run is then excluded, never scored as a miss.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_operators_transform.py
import copy
from sabot.operators import apply, OPERATORS, OperatorResult


def test_registry_has_all_six_with_kinds():
    assert set(OPERATORS) == {"O1", "O2", "O3", "O4", "O5", "O6"}
    assert OPERATORS["O4"].kind == "config"
    assert all(OPERATORS[o].kind == "payload" for o in ("O1", "O2", "O3", "O5", "O6"))


def test_o1_tool_lie_swaps_target_value():
    payload = {"tool": "loader", "result": "vibration reading 47.1 um rms"}
    r = apply("O1", payload, {"field": "result", "find": "47.1", "replace": "74.1"})
    assert r.verified is True
    assert r.payload["result"] == "vibration reading 74.1 um rms"


def test_o1_unlandable_returns_unverified_not_silent():
    payload = {"tool": "loader", "result": "no such number here"}
    r = apply("O1", payload, {"field": "result", "find": "47.1", "replace": "74.1"})
    assert r.verified is False
    assert r.payload == payload  # untouched


def test_o3_message_alteration_same_mechanics_different_semantics():
    payload = {"text": "unit P-3117-D disposition: monitor"}
    r = apply("O3", payload, {"field": "text", "find": "P-3117-D", "replace": "P-3117-B"})
    assert r.verified and "P-3117-B" in r.payload["text"]


def test_o5_stale_context_appends_stale_block():
    payload = {"context": "Rev C: reading 41.7"}
    r = apply("O5", payload, {"field": "context", "stale_content": "Rev A: reading 39.2"})
    assert r.verified is True
    assert r.payload["context"].startswith("Rev C: reading 41.7")
    assert "Rev A: reading 39.2" in r.payload["context"]


def test_purity_input_never_mutated():
    payload = {"result": "47.1", "nested": {"keep": 1}}
    before = copy.deepcopy(payload)
    apply("O1", payload, {"field": "result", "find": "47.1", "replace": "74.1"})
    assert payload == before


def test_unknown_operator_raises():
    try:
        apply("O9", {}, {})
        assert False, "expected KeyError"
    except KeyError:
        pass
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/test_operators_transform.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.operators'`

- [ ] **Step 3: Implement (O1/O3/O5 + registry skeleton; O2/O4/O6 raise NotImplementedError until Task 3)**

```python
"""Fault operators O1-O6 (SPEC section 4). Pure: input payload is never mutated.

An operator that cannot land its corruption returns verified=False — the runner
excludes that cell as INJECTION_UNVERIFIED. This is the blind-oracle lesson:
verify the channel, never assume the fault arrived."""
from __future__ import annotations
import copy
from collections import namedtuple
from dataclasses import dataclass

Operator = namedtuple("Operator", "id kind fn")


@dataclass(frozen=True)
class OperatorResult:
    payload: dict
    verified: bool


def _substring_swap(payload: dict, spec: dict) -> OperatorResult:
    field, find, replace = spec["field"], spec["find"], spec["replace"]
    text = payload.get(field, "")
    if not isinstance(text, str) or find not in text:
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = text.replace(find, replace, 1)
    return OperatorResult(payload=new, verified=True)


def _o5_stale_context(payload: dict, spec: dict) -> OperatorResult:
    field = spec["field"]
    if field not in payload or not isinstance(payload[field], str):
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = new[field] + "\n" + spec["stale_content"]
    return OperatorResult(payload=new, verified=True)


def _todo(payload: dict, spec: dict) -> OperatorResult:  # replaced in Task 3
    raise NotImplementedError


OPERATORS: dict[str, Operator] = {
    "O1": Operator("O1", "payload", _substring_swap),
    "O2": Operator("O2", "payload", _todo),
    "O3": Operator("O3", "payload", _substring_swap),
    "O4": Operator("O4", "config", _todo),
    "O5": Operator("O5", "payload", _o5_stale_context),
    "O6": Operator("O6", "payload", _todo),
}


def apply(operator_id: str, payload: dict, spec: dict) -> OperatorResult:
    return OPERATORS[operator_id].fn(payload, spec)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && python -m pytest tests/test_operators_transform.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/operators.py tests/test_operators_transform.py && git commit -m "feat: operators O1/O3/O5 + registry (pure, verified-injection)"
```

### Task 3: replacement + config operators — O2, O6, O4

**Files:**
- Modify: `~/sabot-harness/sabot/operators.py` (replace the three `_todo` entries)
- Test: `~/sabot-harness/tests/test_operators_replace.py`

**Interfaces:**
- Consumes: Task 2's registry and `OperatorResult`.
- Produces: O2/O6 payload replacements; O4 returns `OperatorResult(payload={"model_override": spec["downgrade_to"]}, verified=True)` — the adapter consumes `model_override` at run setup (Phase 3); the runner treats `kind=="config"` operators as pre-run mutations, not mid-flight ones.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_operators_replace.py
from sabot.operators import apply


def test_o2_false_success_replaces_report():
    payload = {"tool": "reviewer", "result": "3 issues found: ..."}
    r = apply("O2", payload, {"field": "result", "fake_report": "review complete, no issues"})
    assert r.verified is True
    assert r.payload["result"] == "review complete, no issues"
    assert r.payload["tool"] == "reviewer"


def test_o2_missing_field_unverified():
    r = apply("O2", {"other": 1}, {"field": "result", "fake_report": "ok"})
    assert r.verified is False


def test_o6_silent_noop_fakes_done_and_flags_suppression():
    payload = {"tool": "writer", "result": "wrote 8 records"}
    r = apply("O6", payload, {"field": "result", "success_response": "done",
                              "suppress_side_effect": True})
    assert r.verified is True
    assert r.payload["result"] == "done"
    assert r.payload["__sabot_suppress_side_effect__"] is True


def test_o4_model_downgrade_is_config_mutation():
    r = apply("O4", {}, {"downgrade_to": "weaker-model-id"})
    assert r.verified is True
    assert r.payload == {"model_override": "weaker-model-id"}
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/test_operators_replace.py -q`
Expected: FAIL with `NotImplementedError`

- [ ] **Step 3: Implement — replace the `_todo` entries**

```python
def _field_replace(payload: dict, spec: dict, value_key: str,
                   extra: dict | None = None) -> OperatorResult:
    field = spec["field"]
    if field not in payload:
        return OperatorResult(payload=payload, verified=False)
    new = copy.deepcopy(payload)
    new[field] = spec[value_key]
    if extra:
        new.update(extra)
    return OperatorResult(payload=new, verified=True)


def _o2_false_success(payload: dict, spec: dict) -> OperatorResult:
    return _field_replace(payload, spec, "fake_report")


def _o6_silent_noop(payload: dict, spec: dict) -> OperatorResult:
    return _field_replace(payload, spec, "success_response",
                          extra={"__sabot_suppress_side_effect__": True})


def _o4_model_downgrade(payload: dict, spec: dict) -> OperatorResult:
    return OperatorResult(payload={"model_override": spec["downgrade_to"]}, verified=True)
```

And update the registry entries:

```python
    "O2": Operator("O2", "payload", _o2_false_success),
    "O4": Operator("O4", "config", _o4_model_downgrade),
    "O6": Operator("O6", "payload", _o6_silent_noop),
```

Delete `_todo`.

- [ ] **Step 4: Run full suite to verify pass**

Run: `cd ~/sabot-harness && python -m pytest tests/ -q`
Expected: all tests pass (Tasks 1-3 + trace: 19 total), no warnings.

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/operators.py tests/test_operators_replace.py && git commit -m "feat: operators O2/O6/O4 complete the registry"
```

### Task 4: `score.py` — the funnel scorer

**Files:**
- Create: `~/sabot-harness/sabot/score.py`
- Test: `~/sabot-harness/tests/test_score.py`

**Interfaces:**
- Consumes: `sabot.acts.hard_acts`, `DetectionAct`; `sabot.trace.Trace`.
- Produces: `EXCLUSION_CODES = ("BASELINE_FAIL", "RUN_ERROR", "INJECTION_UNVERIFIED")`; `@dataclass(frozen=True) CellVerdict(detected_hard: bool, reacted: bool, recovered: bool, excluded: str | None, acts: tuple[DetectionAct, ...])`; `score(trace: Trace, injection_seq: int, baseline_passed: bool, task_passed: bool, injection_verified: bool, run_error: bool = False) -> CellVerdict`. Phase-4 report aggregates CellVerdicts; Phase-3 judge augments soft tier separately — nothing here changes for it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_score.py
from sabot.trace import Event, Trace
from sabot.score import score, CellVerdict, EXCLUSION_CODES


def _trace_with(events):
    t = Trace(run_id="r", framework="crewai", task="T2", config="default",
              operator="O2", seed=3)
    for e in events:
        t.add(e)
    return t


def _reject(seq):
    return Event(kind="guardrail-event", agent="qa",
                 payload={"act": "reject", "component": "qa", "reason": "report absent"},
                 seq=seq)


def test_exclusion_codes_frozen():
    assert EXCLUSION_CODES == ("BASELINE_FAIL", "RUN_ERROR", "INJECTION_UNVERIFIED")


def test_baseline_fail_excludes_before_anything_else():
    v = score(_trace_with([_reject(5)]), injection_seq=3, baseline_passed=False,
              task_passed=True, injection_verified=True)
    assert v.excluded == "BASELINE_FAIL"
    assert v.detected_hard is False and v.acts == ()


def test_injection_unverified_excludes():
    v = score(_trace_with([]), injection_seq=3, baseline_passed=True,
              task_passed=True, injection_verified=False)
    assert v.excluded == "INJECTION_UNVERIFIED"


def test_run_error_excludes():
    v = score(_trace_with([]), injection_seq=1, baseline_passed=True,
              task_passed=False, injection_verified=True, run_error=True)
    assert v.excluded == "RUN_ERROR"


def test_detected_hard_implies_reacted_and_records_acts():
    v = score(_trace_with([_reject(5)]), injection_seq=3, baseline_passed=True,
              task_passed=True, injection_verified=True)
    assert v.excluded is None
    assert v.detected_hard is True and v.reacted is True
    assert len(v.acts) == 1 and v.acts[0].seq == 5


def test_pre_injection_act_does_not_detect():
    v = score(_trace_with([_reject(2)]), injection_seq=3, baseline_passed=True,
              task_passed=False, injection_verified=True)
    assert v.detected_hard is False and v.reacted is False


def test_lucky_recovery_scored_recovered_not_detected():
    v = score(_trace_with([]), injection_seq=1, baseline_passed=True,
              task_passed=True, injection_verified=True)
    assert v.excluded is None
    assert v.detected_hard is False and v.recovered is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/test_score.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.score'`

- [ ] **Step 3: Implement `sabot/score.py`**

```python
"""Funnel scorer (SPEC section 2-3). Pure: trace + run facts in, verdict out.
The hard tier only — the soft-tier judge (Phase 3) reports separately and can
never alter these fields. Exclusion precedence: RUN_ERROR, then BASELINE_FAIL,
then INJECTION_UNVERIFIED; an excluded cell scores nothing."""
from __future__ import annotations
from dataclasses import dataclass
from sabot.acts import DetectionAct, hard_acts
from sabot.trace import Trace

EXCLUSION_CODES = ("BASELINE_FAIL", "RUN_ERROR", "INJECTION_UNVERIFIED")


@dataclass(frozen=True)
class CellVerdict:
    detected_hard: bool
    reacted: bool
    recovered: bool
    excluded: str | None
    acts: tuple[DetectionAct, ...]


def _excluded(code: str) -> CellVerdict:
    return CellVerdict(detected_hard=False, reacted=False, recovered=False,
                       excluded=code, acts=())


def score(trace: Trace, injection_seq: int, baseline_passed: bool,
          task_passed: bool, injection_verified: bool,
          run_error: bool = False) -> CellVerdict:
    if run_error:
        return _excluded("RUN_ERROR")
    if not baseline_passed:
        return _excluded("BASELINE_FAIL")
    if not injection_verified:
        return _excluded("INJECTION_UNVERIFIED")
    acts = tuple(hard_acts(trace, since_seq=injection_seq))
    detected = bool(acts)
    return CellVerdict(detected_hard=detected,
                       reacted=detected,  # hard acts are corrective by SPEC section 2
                       recovered=task_passed,
                       excluded=None,
                       acts=acts)
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && python -m pytest tests/test_score.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/score.py tests/test_score.py && git commit -m "feat: funnel scorer - exclusion precedence, post-injection detection, hard tier only"
```

### Task 5: `runner.py` — Adapter protocol + cell orchestration

**Files:**
- Create: `~/sabot-harness/sabot/runner.py`
- Test: `~/sabot-harness/tests/test_runner.py`

**Interfaces:**
- Consumes: `sabot.score.score`, `CellVerdict`; `sabot.trace.Trace`.
- Produces: `@dataclass(frozen=True) Cell(framework, task, config, operator, operator_spec, seed)` (operator may be None = baseline); `@dataclass RunResult(trace: Trace, task_passed: bool, injection_seq: int | None, injection_verified: bool, error: str | None = None)`; `class Adapter(Protocol)` with `run(cell: Cell) -> RunResult`; `run_cell(adapter: Adapter, cell: Cell, faulted: RunResult, baseline: RunResult) -> CellVerdict`. Phase 3 implements Adapter per framework; Phase 4's matrix driver loops `run_cell`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner.py
from sabot.trace import Event, Trace
from sabot.runner import Cell, RunResult, run_cell


class FakeAdapter:
    """Runner never calls the adapter in run_cell (results are passed in);
    this fake exists to prove the protocol shape imports and instantiates."""
    def run(self, cell):
        raise AssertionError("run_cell must not re-run the adapter")


def _result(events=(), task_passed=True, injection_seq=2, verified=True, error=None,
            operator="O1"):
    t = Trace(run_id="r", framework="langgraph", task="T1", config="default",
              operator=operator, seed=1)
    for e in events:
        t.add(e)
    return RunResult(trace=t, task_passed=task_passed, injection_seq=injection_seq,
                     injection_verified=verified, error=error)


def _cell(operator="O1"):
    return Cell(framework="langgraph", task="T1", config="default",
                operator=operator, operator_spec={"field": "r", "find": "a", "replace": "b"},
                seed=1)


def test_faulted_cell_scores_against_baseline_pass():
    baseline = _result(operator=None, injection_seq=None)
    faulted = _result(events=[Event(kind="guardrail-event", agent="rev",
                                    payload={"act": "reject", "component": "rev",
                                             "reason": "mismatch"}, seq=3)])
    v = run_cell(FakeAdapter(), _cell(), faulted, baseline)
    assert v.excluded is None and v.detected_hard is True


def test_failed_baseline_poisons_the_cell():
    baseline = _result(operator=None, injection_seq=None, task_passed=False)
    v = run_cell(FakeAdapter(), _cell(), _result(), baseline)
    assert v.excluded == "BASELINE_FAIL"


def test_adapter_error_maps_to_run_error():
    baseline = _result(operator=None, injection_seq=None)
    v = run_cell(FakeAdapter(), _cell(), _result(error="api timeout"), baseline)
    assert v.excluded == "RUN_ERROR"


def test_missing_injection_seq_on_faulted_run_is_unverified():
    baseline = _result(operator=None, injection_seq=None)
    v = run_cell(FakeAdapter(), _cell(), _result(injection_seq=None), baseline)
    assert v.excluded == "INJECTION_UNVERIFIED"
```

Note the `run_cell(adapter, cell, faulted, baseline)` signature the tests pin.

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/test_runner.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.runner'`

- [ ] **Step 3: Implement `sabot/runner.py`**

```python
"""Adapter protocol + cell scoring seam. The runner is deliberately thin: adapters
own all IO and framework contact; run_cell only turns two RunResults into a verdict.
The Phase-4 matrix driver owns looping, retries, and trace persistence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from sabot.score import CellVerdict, score
from sabot.trace import Trace


@dataclass(frozen=True)
class Cell:
    framework: str
    task: str
    config: str
    operator: str | None
    operator_spec: dict | None
    seed: int


@dataclass
class RunResult:
    trace: Trace
    task_passed: bool
    injection_seq: int | None
    injection_verified: bool
    error: str | None = None


class Adapter(Protocol):
    def run(self, cell: Cell) -> RunResult: ...


def run_cell(adapter: Adapter, cell: Cell, faulted: RunResult,
             baseline: RunResult) -> CellVerdict:
    run_error = faulted.error is not None or baseline.error is not None
    injection_verified = faulted.injection_verified and faulted.injection_seq is not None
    return score(trace=faulted.trace,
                 injection_seq=faulted.injection_seq or 0,
                 baseline_passed=baseline.task_passed,
                 task_passed=faulted.task_passed,
                 injection_verified=injection_verified,
                 run_error=run_error)
```

- [ ] **Step 4: Run full suite**

Run: `cd ~/sabot-harness && python -m pytest tests/ -q`
Expected: all pass (Tasks 1-5 + trace: 30 total), pristine output.

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/runner.py tests/test_runner.py && git commit -m "feat: adapter protocol + run_cell scoring seam"
```

### Task 6: mutation hardening — zero unexplained survivors

**Files:**
- Modify: `~/sabot-harness/pyproject.toml` (mutmut dev dep + scope)
- Possibly modify: `sabot/acts.py`, `sabot/operators.py`, `sabot/score.py`, their tests (killing survivors)

**Interfaces:**
- Consumes: everything above. Produces: the evidence that the scoring core meets the SPEC's own bar before any data is collected.

- [ ] **Step 1: Configure mutmut scope**

Append to `pyproject.toml`:

```toml
[tool.mutmut]
paths_to_mutate = ["sabot/acts.py", "sabot/operators.py", "sabot/score.py"]
```

Add `"mutmut>=3"` to the dev extras list. Install: `cd ~/sabot-harness && python -m pip install -e '.[dev]'`

- [ ] **Step 2: Run mutation testing**

Run: `cd ~/sabot-harness && python -m mutmut run`
Then: `python -m mutmut results`
Record the counts (killed / survived / no-tests).

- [ ] **Step 3: Kill survivors**

For each surviving mutant: read it (`python -m mutmut show <id>`), write the test that kills it (real behavioral assertion — `==` on exact values, never bare substring-in checks, the oracle-gate lesson), re-run. Iterate until `results` lists zero survivors in the three scoped files, OR a survivor is genuinely equivalent.

- [ ] **Step 4: STOP-gate for equivalents**

If any survivor is judged equivalent: do NOT write an exemption. STOP, present the mutant diff and the equivalence argument to Jeff (he signs, or the dead code gets deleted instead — prefer deletion per the graph-guard precedent).

- [ ] **Step 5: Record and commit**

Append the final counts to `~/sabot-harness/MUTATION.md` (create it: date, per-file killed/survived/no-tests, any Jeff-signed survivors, the honest denominator). Then:

```bash
cd ~/sabot-harness && git add -A && git commit -m "test: mutation-harden core to zero unexplained survivors (MUTATION.md receipts)"
```
