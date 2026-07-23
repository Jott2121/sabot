import json
from sabot.trace import Event, Trace
from sabot.runner import RunResult
from sabot.score import CellVerdict
from sabot.acts import DetectionAct
from sabot.serde import (run_result_to_json, run_result_from_json,
                         cell_verdict_to_json, cell_verdict_from_json)


def _trace():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator="O1", seed=1)
    t.add(Event(kind="tool-call", agent="loader",
                payload={"tool": "load_document", "injected": True}, seq=1))
    return t


def test_run_result_round_trip():
    r = RunResult(trace=_trace(), task_passed=True, injection_seq=1,
                  injection_verified=True, error=None)
    back = run_result_from_json(run_result_to_json(r))
    assert back.task_passed is True and back.injection_seq == 1
    assert back.injection_verified is True and back.error is None
    assert back.trace.to_json() == r.trace.to_json()


def test_run_result_round_trip_error_and_none_seq():
    r = RunResult(trace=_trace(), task_passed=False, injection_seq=None,
                  injection_verified=False, error="api timeout")
    back = run_result_from_json(run_result_to_json(r))
    assert back.injection_seq is None and back.error == "api timeout"


def test_cell_verdict_round_trip_with_acts():
    v = CellVerdict(detected_hard=True, reacted=True, recovered=False, excluded=None,
                    acts=(DetectionAct(component="reviewer", act="reject",
                                       reason="id mismatch", seq=4),))
    back = cell_verdict_from_json(cell_verdict_to_json(v))
    assert back == v


def test_run_result_to_json_keys_are_sorted_alphabetically():
    r = RunResult(trace=_trace(), task_passed=True, injection_seq=1,
                  injection_verified=True, error=None)
    expected = json.dumps({
        "trace": json.loads(r.trace.to_json()),
        "task_passed": r.task_passed,
        "injection_seq": r.injection_seq,
        "injection_verified": r.injection_verified,
        "error": r.error,
    }, sort_keys=True)
    assert run_result_to_json(r) == expected


def test_cell_verdict_to_json_keys_are_sorted_alphabetically():
    v = CellVerdict(detected_hard=True, reacted=False, recovered=True, excluded=None, acts=())
    expected = json.dumps({
        "detected_hard": v.detected_hard, "reacted": v.reacted,
        "recovered": v.recovered, "excluded": v.excluded,
        "acts": [],
    }, sort_keys=True)
    assert cell_verdict_to_json(v) == expected


def test_cell_verdict_from_json_preserves_non_none_excluded():
    v = CellVerdict(detected_hard=False, reacted=None, recovered=None, excluded="live_a", acts=())
    back = cell_verdict_from_json(cell_verdict_to_json(v))
    assert back.excluded == "live_a"
