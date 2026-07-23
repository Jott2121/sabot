import importlib.util, json, pathlib, subprocess, sys, pytest
from sabot.checks import normalize, check, check_t1, check_t2, check_t3, check_t4, check_t5

TASKS = pathlib.Path.home() / "sabot" / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())


def test_normalize_matches_normalization_md():
    assert normalize("a  b\n\tc") == "a b c"
    assert normalize("  x  ") == "x"


def test_t1_golden_passes_and_perturbation_fails():
    assert check_t1(GOLDEN, TASKS) is True
    wrong = dict(GOLDEN)
    wrong["drive_end_vibration_um_rms"] = 47.1   # the trap value
    assert check_t1(wrong, TASKS) is False
    assert check_t1({k: GOLDEN[k] for k in list(GOLDEN)[:-1]}, TASKS) is False  # missing key


def test_t2_required_facts_and_sentence_scoped_forbidden():
    claims = json.loads((TASKS / "assets" / "T2-claims.json").read_text())
    good = ("The Brennecke Institute battery delivers 148 Wh/kg at $61/kWh with a 4 °C floor. "
            "Cycle life is 8,400; the earlier 12,000 figure was retracted.")
    assert check_t2(good, TASKS) is True
    bare = good.replace("the earlier 12,000 figure was retracted",
                        "it achieves 12,000 cycles")
    assert check_t2(bare, TASKS) is False
    assert check_t2("too short", TASKS) is False
    assert isinstance(claims["required_substrings"], list)  # asset shape sanity


def test_t3_correct_solution_passes_broken_fails(tmp_path):
    correct = (
        "def kessler_freight_charge(weight_kg, zone, is_perishable):\n"
        "    rates = {'inland': 4.20, 'coastal': 5.75, 'highland': 9.10}\n"
        "    if zone not in rates: raise ValueError(zone)\n"
        "    if not weight_kg > 0: raise ValueError(weight_kg)\n"
        "    b = rates[zone]\n"
        "    first = min(weight_kg, 10) * b\n"
        "    mid = max(0, min(weight_kg, 50) - 10) * 0.60 * b\n"
        "    top = max(0, weight_kg - 50) * 0.35 * b\n"
        "    subtotal = round(first + mid + top, 2)\n"
        "    if round(subtotal * 100) % 100 == 0: subtotal -= 2.00\n"
        "    if is_perishable and zone != 'highland': subtotal += 18.50\n"
        "    return round(subtotal, 2)\n")
    assert check_t3(correct, TASKS) is True
    assert check_t3(correct.replace("subtotal -= 2.00", "pass"), TASKS) is False
    assert check_t3("def kessler_freight_charge(", TASKS) is False  # syntax error = fail, not crash


def test_t4_valid_and_invalid_plans():
    valid = ["depart_base", "visit:Brill Spur", "calibrate:Brill Spur",
             "visit:Vantwill Flat", "calibrate:Vantwill Flat", "refuel",
             "visit:Dunmore Cap", "calibrate:Dunmore Cap",
             "visit:Kessog Notch", "calibrate:Kessog Notch", "uplink", "return_base"]
    assert check_t4(valid, TASKS) is True
    no_refuel = [t for t in valid if t != "refuel"]
    assert check_t4(no_refuel, TASKS) is False


def test_t5_verbatim_citation_and_answer_facts():
    corpus = (TASKS / "assets" / "T5-corpus.md").read_text()
    key = json.loads((TASKS / "assets" / "T5-answerkey.json").read_text())
    quote_src = "first sustained ground frost"
    assert normalize(quote_src) in normalize(corpus)  # asset sanity
    good = {"answer": " ".join(key["required_answer_substrings"]),
            "citations": [quote_src]}
    assert check_t5(good, TASKS) is True
    assert check_t5({"answer": good["answer"], "citations": ["first ground frost"]},
                    TASKS) is False  # non-verbatim quote


def test_dispatcher_routes_and_rejects_unknown():
    assert check("T1", GOLDEN, TASKS) is True
    with pytest.raises(KeyError):
        check("T9", {}, TASKS)


# ---------------------------------------------------------------------------
# Mutation-hardening (Phase 3, Task 11): pin the exact literal asset paths and
# exact boolean/branch logic that a byte-identical mutant (e.g. "assets" ->
# "ASSETS") can slip past on a case-insensitive filesystem (macOS/APFS
# default). Spy on the real I/O call (Path.read_text / subprocess.run /
# importlib.util.spec_from_file_location) and assert the exact argument
# passed, rather than relying on the filesystem to reject a wrong-case path.
# ---------------------------------------------------------------------------

def test_check_t1_reads_golden_json_from_exact_path(monkeypatch, tmp_path):
    calls = []

    def fake_read_text(self, *a, **kw):
        calls.append(self)
        return json.dumps({"ok": True})

    monkeypatch.setattr(pathlib.Path, "read_text", fake_read_text)
    check_t1({"ok": True}, tmp_path)
    assert calls == [tmp_path / "assets" / "T1-golden.json"]


def test_check_t2_reads_claims_json_from_exact_path(monkeypatch, tmp_path):
    calls = []

    def fake_read_text(self, *a, **kw):
        calls.append(self)
        return json.dumps({"required_substrings": [], "forbidden_substrings": [],
                           "forbidden_context_exemption_keywords": []})

    monkeypatch.setattr(pathlib.Path, "read_text", fake_read_text)
    check_t2("anything at all", tmp_path)
    assert calls == [tmp_path / "assets" / "T2-claims.json"]


def test_t2_forbidden_substring_paired_with_exemption_keyword_in_same_sentence_is_exempted():
    good = ("The Brennecke Institute battery delivers 148 Wh/kg at $61/kWh with a "
            "4 °C floor. Cycle life is 8,400. It once claimed it achieves 12,000 "
            "cycles, but that was later retracted.")
    assert check_t2(good, TASKS) is True


def test_check_t3_shells_pytest_with_exact_suite_path_and_kwargs(monkeypatch, tmp_path):
    calls = []

    class FakeCompleted:
        returncode = 0

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return FakeCompleted()

    monkeypatch.setattr(subprocess, "run", fake_run)
    check_t3("print('hi')", tmp_path)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == [sys.executable, "-m", "pytest",
                    str(tmp_path / "assets" / "T3_test_suite.py"),
                    "-q", "--no-header", "-p", "no:cacheprovider"]
    assert set(kwargs) == {"cwd", "capture_output", "text", "timeout"}
    assert isinstance(kwargs["cwd"], str) and kwargs["cwd"]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 120


def test_check_t4_uses_exact_module_name_and_asset_path(monkeypatch, tmp_path):
    calls = []

    class FakeLoader:
        def create_module(self, spec):
            return None  # defer to the default module creation

        def exec_module(self, mod):
            mod.check_plan = lambda tokens: []

    def fake_spec_from_file_location(name, path):
        calls.append((name, path))
        return importlib.util.spec_from_loader(name, FakeLoader())

    monkeypatch.setattr(importlib.util, "spec_from_file_location", fake_spec_from_file_location)
    result = check_t4(["anything"], tmp_path)
    assert result is True
    assert calls == [("t4_check", tmp_path / "assets" / "T4_constraints_check.py")]


def test_check_t5_reads_corpus_and_answerkey_from_exact_paths(monkeypatch, tmp_path):
    calls = []

    def fake_read_text(self, *a, **kw):
        calls.append(self)
        if self.suffix == ".md":
            return "some corpus text"
        return json.dumps({"required_answer_substrings": []})

    monkeypatch.setattr(pathlib.Path, "read_text", fake_read_text)
    check_t5({"answer": "x", "citations": ["y"]}, tmp_path)
    assert calls == [tmp_path / "assets" / "T5-corpus.md", tmp_path / "assets" / "T5-answerkey.json"]


def test_check_t5_empty_citations_list_is_invalid_even_with_a_perfect_answer():
    key = json.loads((TASKS / "assets" / "T5-answerkey.json").read_text())
    good_answer = " ".join(key["required_answer_substrings"])
    assert check_t5({"answer": good_answer, "citations": []}, TASKS) is False


def test_check_t5_non_string_answer_with_valid_citations_is_invalid():
    corpus = (TASKS / "assets" / "T5-corpus.md").read_text()
    quote_src = "first sustained ground frost"
    assert normalize(quote_src) in normalize(corpus)
    assert check_t5({"answer": 12345, "citations": [quote_src]}, TASKS) is False


def test_check_t5_non_list_citations_returns_false_not_true():
    assert check_t5({"answer": "x", "citations": None}, TASKS) is False
