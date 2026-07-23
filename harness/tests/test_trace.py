import json
from sabot.trace import Event, Trace

def test_event_roundtrip():
    e = Event(kind="tool-call", agent="extractor", payload={"tool": "loader"}, seq=1)
    assert Event.from_dict(e.to_dict()) == e

def test_trace_roundtrip_and_order():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator="O1", seed=3)
    t.add(Event(kind="agent-msg", agent="extractor", payload={"text": "hi"}, seq=1))
    t.add(Event(kind="guardrail-event", agent="reviewer",
                payload={"act": "reject", "reason": "id mismatch"}, seq=2))
    s = t.to_json()
    t2 = Trace.from_json(s)
    assert t2 == t
    assert [e.seq for e in t2.events] == [1, 2]
    assert json.loads(s)["schema_version"] == 1

def test_trace_rejects_out_of_order_seq():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator=None, seed=0)
    t.add(Event(kind="agent-msg", agent="a", payload={}, seq=2))
    try:
        t.add(Event(kind="agent-msg", agent="a", payload={}, seq=1))
        assert False, "expected ValueError"
    except ValueError:
        pass
