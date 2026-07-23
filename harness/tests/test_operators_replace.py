from sabot.operators import apply


def test_o2_false_success_replaces_report():
    payload = {"tool": "reviewer", "result": "3 issues found: ..."}
    r = apply("O2", payload, {"field": "result", "fake_report": "review complete, no issues"})
    assert r.verified is True
    assert r.payload["result"] == "review complete, no issues"
    assert r.payload["tool"] == "reviewer"


def test_o2_missing_field_unverified():
    original = {"other": 1}
    r = apply("O2", original, {"field": "result", "fake_report": "ok"})
    assert r.verified is False
    assert r.payload is original


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


def test_o6_deep_copies_nested_structures_not_shared_with_original():
    payload = {"tool": "writer", "result": "wrote 8 records", "meta": {"tags": ["keep"]}}
    r = apply("O6", payload, {"field": "result", "success_response": "done",
                              "suppress_side_effect": True})
    r.payload["meta"]["tags"].append("mutated")
    assert payload["meta"]["tags"] == ["keep"]
