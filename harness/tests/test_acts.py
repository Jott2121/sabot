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


def test_unknown_act_error_message_names_the_bad_act():
    t = _trace([_guardrail(1, "vetoed")])
    try:
        hard_acts(t)
        assert False, "expected ValueError"
    except ValueError as e:
        assert str(e) == "unknown guardrail act: 'vetoed'"


def test_default_since_seq_is_zero_includes_seq_zero_act():
    t = _trace([_guardrail(0, "reject")])
    assert [a.seq for a in hard_acts(t)] == [0]
