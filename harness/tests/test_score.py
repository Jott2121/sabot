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


def test_excluded_verdict_has_no_detection_reaction_or_recovery():
    v = score(_trace_with([]), injection_seq=1, baseline_passed=False,
              task_passed=True, injection_verified=True)
    assert v == CellVerdict(detected_hard=False, reacted=False, recovered=False,
                            excluded="BASELINE_FAIL", acts=())
