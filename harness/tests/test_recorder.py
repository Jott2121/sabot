from sabot.adapters.recorder import TraceRecorder
from sabot.trace import Event


def _r(operator="O1"):
    return TraceRecorder(run_id="r", framework="langgraph", task="T1",
                         config="default", operator=operator, seed=1)


def test_seq_is_monotonic_across_event_kinds():
    r = _r()
    s1 = r.agent_msg("extractor", "hello")
    s2 = r.tool_call("extractor", "load_document", {"result": "body"})
    s3 = r.guardrail("reviewer", "reject", "value conflicts with caption")
    assert (s1, s2, s3) == (1, 2, 3)
    assert [e.seq for e in r.trace.events] == [1, 2, 3]


def test_inject_lands_and_marks_event():
    r = _r()
    payload = {"result": "vibration reading 47.1 um rms"}
    faulted, seq, verified = r.inject("O1", payload,
                                      {"field": "result", "find": "47.1", "replace": "74.1"},
                                      agent="loader", tool="load_document")
    assert verified is True and seq == 1
    assert "74.1" in faulted["result"]
    ev = r.trace.events[0]
    assert ev.kind == "tool-call" and ev.payload["injected"] is True


def test_inject_unlandable_returns_unverified_and_untouched():
    r = _r()
    payload = {"result": "no target here"}
    faulted, seq, verified = r.inject("O1", payload,
                                      {"field": "result", "find": "47.1", "replace": "74.1"},
                                      agent="loader", tool="load_document")
    assert verified is False and faulted == payload
    assert seq is not None  # the attempt is still on the trace for the audit record


def test_guardrail_event_payload_matches_frozen_contract():
    r = _r()
    r.guardrail("qa", "reject", "report absent")
    p = r.trace.events[0].payload
    assert p == {"act": "reject", "component": "qa", "reason": "report absent"}


def test_init_stores_all_constructor_fields_on_trace():
    r = TraceRecorder(run_id="run-1", framework="crewai", task="T3",
                      config="cfgX", operator="O5", seed=7)
    t = r.trace
    assert t.run_id == "run-1"
    assert t.framework == "crewai"
    assert t.task == "T3"
    assert t.config == "cfgX"
    assert t.operator == "O5"
    assert t.seed == 7


def test_guardrail_event_agent_is_the_component():
    r = _r()
    r.guardrail("qa", "reject", "report absent")
    assert r.trace.events[0].agent == "qa"


def test_agent_msg_event_exact_fields():
    r = _r()
    seq = r.agent_msg("extractor", "hello world")
    assert seq == 1
    assert r.trace.events[0] == Event(kind="agent-msg", agent="extractor",
                                      payload={"text": "hello world"}, seq=1)


def test_tool_call_default_injected_false_and_exact_fields():
    r = _r()
    seq = r.tool_call("extractor", "load_document", {"result": "body"})
    assert seq == 1
    assert r.trace.events[0] == Event(
        kind="tool-call", agent="extractor",
        payload={"tool": "load_document", "injected": False, "result": "body"}, seq=1)


def test_verdict_emits_kind_agent_payload_exact():
    r = _r()
    seq = r.verdict("judge", {"noticed": True})
    assert seq == 1
    assert r.trace.events[0] == Event(kind="verdict", agent="judge",
                                      payload={"noticed": True}, seq=1)


def test_inject_tool_call_event_has_exact_agent_tool_and_operator_key():
    r = _r()
    payload = {"result": "no target here"}
    r.inject("O1", payload, {"field": "result", "find": "nomatch", "replace": "x"},
             agent="loader", tool="load_document")
    ev = r.trace.events[0]
    assert ev.agent == "loader"
    assert ev.payload == {"tool": "load_document", "injected": True, "operator": "O1"}
