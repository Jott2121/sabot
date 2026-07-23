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


def test_o1_field_absent_treated_as_empty_string_with_empty_find():
    # payload.get(field, "") is the fallback when the field is entirely absent;
    # an empty find matches an empty string at position 0, so the field gets
    # created with exactly the replace value (no other artifact left behind).
    r = apply("O1", {"other": 1}, {"field": "result", "find": "", "replace": "INSERTED"})
    assert r.verified is True
    assert r.payload == {"other": 1, "result": "INSERTED"}


def test_o1_replaces_only_the_first_occurrence():
    payload = {"result": "47.1 47.1 47.1"}
    r = apply("O1", payload, {"field": "result", "find": "47.1", "replace": "X"})
    assert r.payload["result"] == "X 47.1 47.1"


def test_o1_deep_copies_nested_structures_not_shared_with_original():
    payload = {"result": "47.1", "meta": {"tags": ["keep"]}}
    r = apply("O1", payload, {"field": "result", "find": "47.1", "replace": "74.1"})
    r.payload["meta"]["tags"].append("mutated")
    assert payload["meta"]["tags"] == ["keep"]


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


def test_o5_joins_stale_content_with_exact_newline_separator():
    payload = {"context": "Rev C: reading 41.7"}
    r = apply("O5", payload, {"field": "context", "stale_content": "Rev A: reading 39.2"})
    assert r.payload["context"] == "Rev C: reading 41.7\nRev A: reading 39.2"


def test_o5_field_present_but_non_string_is_unverified():
    payload = {"context": 123}
    r = apply("O5", payload, {"field": "context", "stale_content": "stale"})
    assert r.verified is False
    assert r.payload is payload


def test_o5_field_missing_returns_original_payload_unverified():
    payload = {"other": 1}
    r = apply("O5", payload, {"field": "context", "stale_content": "stale"})
    assert r.verified is False
    assert r.payload is payload


def test_o5_deep_copies_nested_structures_not_shared_with_original():
    payload = {"context": "hello", "meta": {"tags": ["keep"]}}
    r = apply("O5", payload, {"field": "context", "stale_content": "stale"})
    r.payload["meta"]["tags"].append("mutated")
    assert payload["meta"]["tags"] == ["keep"]


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
