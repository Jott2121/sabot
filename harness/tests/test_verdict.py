from sabot.adapters.verdict import parse_verdict


def test_approve_and_reject_tokens():
    assert parse_verdict("VERDICT: APPROVE") == ("APPROVE", "")
    assert parse_verdict("Looks wrong.\nVERDICT: REJECT - unit id mismatch vs source") == \
        ("REJECT", "unit id mismatch vs source")


def test_no_token_returns_none_never_guesses():
    assert parse_verdict("this data looks off but whatever") is None
    assert parse_verdict("") is None


def test_reject_without_reason_still_parses():
    assert parse_verdict("VERDICT: REJECT") == ("REJECT", "")


def test_none_text_searches_empty_string_not_a_placeholder(monkeypatch):
    """`_TOKEN.search(text or "")` must fall back to the empty string, not some other
    placeholder, when text is falsy -- spy on the search call itself since a placeholder
    that also fails to match VERDICT: ... would otherwise be behaviorally invisible."""
    captured = {}

    class FakeToken:
        def search(self, s):
            captured["s"] = s
            return None

    monkeypatch.setattr("sabot.adapters.verdict._TOKEN", FakeToken())
    assert parse_verdict(None) is None
    assert captured["s"] == ""
