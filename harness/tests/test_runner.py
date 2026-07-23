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
