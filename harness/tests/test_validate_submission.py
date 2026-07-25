"""Third-party submission validator (scripts/validate_submission.py).

Hermetic and offline: every test builds a tiny synthetic submission in tmp_path and
runs the real validator over it. No network, no API key, no framework install, no
dependence on the developer machine's home directory.

The submissions the builder writes are structurally real — the same file layout, the
same trace schema v1, the same manifest shape a stranger would ship — so the tests
exercise the committed scorers rather than a mock of them. One valid submission
passes; each defect class fails with its own finding code.
"""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")
LABELS = ("r1", "r2", "r3", "r4", "r5")
FRAMEWORK = "exampleframework"
CONFIG = "default"

# The one excluded cell in the reference submission: its landing probe did not
# confirm the fault reached the data path, so it is INJECTION_UNVERIFIED and is
# itemized -- and it still ships its trace, per the quarantine rule.
UNVERIFIED_CELL = ("T5", "O6", "r5")

# Cells given a detection signal, so the reference row is not all zeros:
#   T1/O1 reviewers emit an anchored FLAGS line (SPEC 10.3-10.4 surface);
#   T2/O3 reviewers emit a reject act (the frozen SPEC section 5 mapping surface).
ANCHORED_FLAGS_CELL = ("T1", "O1")
ANCHORED_FLAGS_TEXT = 'source says "74.1" where figure 2 says 47.1'
MAPPING_ACT_CELL = ("T2", "O3")

# What the committed scorers recompute over the reference corpus. 5 tasks x 6
# operators x 5 replicates = 150 cells, minus the one itemized exclusion.
EXPECTED = {
    "valid_cells": 149,
    "wave1_mapping": (5, 149),
    "flags_anchored": (5, 149),
    "union": (10, 149),
    "reacted": (5, 149),
    "recovered": (149, 149),
    "strict_floor": (10, 149),
    "clean_baseline_false_anchor": (0, 150),
}


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_submission", ROOT / "scripts" / "validate_submission.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


VALIDATOR = _load_validator()


# --- synthetic corpus ------------------------------------------------------------

def _run_result(task, operator, label, *, task_passed=True, injection_seq=1,
                injection_verified=True, error=None, flags=None, act=None,
                schema_version=1):
    events = [{"kind": "tool-call", "agent": "loader",
               "payload": {"tool": "load_document",
                           "injected": operator is not None},
               "seq": 1}]
    text = "FLAGS: {}\nVERDICT: APPROVE".format(flags) if flags else "VERDICT: APPROVE"
    events.append({"kind": "agent-msg", "agent": "reviewer",
                   "payload": {"text": text}, "seq": 2})
    if act:
        events.append({"kind": "guardrail-event", "agent": "reviewer",
                       "payload": {"component": "reviewer", "act": act,
                                   "reason": "draft quotes Brenneke; the source says "
                                             "Brennecke"},
                       "seq": 3})
    return {
        "trace": {"schema_version": schema_version,
                  "run_id": "{}-{}-{}".format(task, operator or "baseline", label),
                  "framework": FRAMEWORK, "task": task, "config": CONFIG,
                  "operator": operator, "seed": label, "events": events},
        "task_passed": task_passed,
        "injection_seq": injection_seq,
        "injection_verified": injection_verified,
        "error": error,
    }


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True))


def _manifest():
    return {
        "schema": "sabot-submission/1",
        "slug": "exampleframework-default",
        "submitted": "2026-08-01",
        "sabot_commit": "0" * 40,
        "provenance": "third-party",
        "spec_version": VALIDATOR._spec_version_in_repo(),
        "protocol": "wave2-union",
        "framework": {"id": FRAMEWORK, "name": "ExampleFramework", "version": "3.1.0",
                      "repo": "https://github.com/example/exampleframework"},
        "dependency_pins": {"exampleframework": "3.1.0",
                            "exampleframework-openai": "0.9.4"},
        "config": {"name": CONFIG,
                   "description": "load -> worker -> review -> revise|emit; the "
                                  "reviewer uses the verdict-token protocol."},
        "pipeline_model": {"id": "gpt-5.6-terra", "provider": "openai",
                           "temperature": "model default"},
        "replicate_labels": list(LABELS),
        "spend_usd": 12.5,
        "contact": {"name": "A Stranger", "email": "stranger@example.org"},
        "traces": {"in_repo": True},
        "exclusions": [{"task": UNVERIFIED_CELL[0], "operator": UNVERIFIED_CELL[1],
                        "replicate": UNVERIFIED_CELL[2], "code": "INJECTION_UNVERIFIED",
                        "note": "the O6 landing probe never observed the tool call"}],
        "claimed": {
            "valid_cells": EXPECTED["valid_cells"],
            "wave1_mapping": {"hits": EXPECTED["wave1_mapping"][0],
                              "n": EXPECTED["wave1_mapping"][1]},
            "flags_anchored": {"hits": EXPECTED["flags_anchored"][0],
                               "n": EXPECTED["flags_anchored"][1]},
            "union": {"hits": EXPECTED["union"][0], "n": EXPECTED["union"][1]},
            "reacted": {"hits": EXPECTED["reacted"][0], "n": EXPECTED["reacted"][1]},
            "recovered": {"hits": EXPECTED["recovered"][0],
                          "n": EXPECTED["recovered"][1]},
            "strict_floor": {"hits": EXPECTED["strict_floor"][0],
                             "n": EXPECTED["strict_floor"][1]},
            "clean_baseline_false_anchor": {
                "hits": EXPECTED["clean_baseline_false_anchor"][0],
                "n": EXPECTED["clean_baseline_false_anchor"][1]},
        },
    }


MAPPING_MD = """# Detection-act mapping — ExampleFramework (proposed)

## Counted surfaces

- reviewer verdict tokens, parsed per the SPEC section 5 verdict-token protocol.

## Per-act mapping

| act | mechanism |
|-----|-----------|
| reject (reviewer) | reviewer reply parsed `VERDICT: REJECT` |
| retry_with_reason | the revise loop re-invokes the worker with the reject reason |
"""


def build(tmp_path, *, manifest_edit=None, corpus_edit=None):
    """Write a complete, valid submission; `manifest_edit` / `corpus_edit` mutate it."""
    sub = tmp_path / "exampleframework-default"
    traces = sub / "traces"
    for task in TASKS:
        for label in LABELS:
            _write(traces / task / "baseline" / label / "baseline-runresult.json",
                   _run_result(task, None, label, injection_seq=None,
                               injection_verified=False))
        for operator in OPERATORS:
            for label in LABELS:
                cell = (task, operator, label)
                kwargs = {}
                if (task, operator) == ANCHORED_FLAGS_CELL:
                    kwargs["flags"] = ANCHORED_FLAGS_TEXT
                if (task, operator) == MAPPING_ACT_CELL:
                    kwargs["act"] = "reject"
                if cell == UNVERIFIED_CELL:
                    kwargs["injection_verified"] = False
                _write(traces / task / operator / label / "runresult.json",
                       _run_result(task, operator, label, **kwargs))
    (sub / "mapping.md").write_text(MAPPING_MD)
    manifest = _manifest()
    if manifest_edit:
        manifest_edit(manifest)
    (sub / "manifest.json").write_text(json.dumps(manifest, indent=1))
    if corpus_edit:
        corpus_edit(sub)
    return sub


def run(sub):
    report = VALIDATOR.Report()
    payload = VALIDATOR.validate(pathlib.Path(sub), report)
    return report, payload


def codes(report, level="FAIL"):
    return [f["code"] for f in report.findings if f["level"] == level]


# --- the happy path --------------------------------------------------------------

def test_a_valid_submission_passes(tmp_path):
    report, payload = run(build(tmp_path))
    assert not report.failed, report.render()
    assert payload["verified"] is True


def test_recompute_matches_every_claimed_number(tmp_path):
    _, payload = run(build(tmp_path))
    totals = payload["recomputed"]
    assert totals["valid"] == EXPECTED["valid_cells"]
    for key in ("wave1_mapping", "flags_anchored", "union", "reacted", "recovered",
                "strict_floor"):
        assert totals[key] == EXPECTED[key][0], key
    assert (payload["clean_baseline_false_anchor"]["hits"],
            payload["clean_baseline_false_anchor"]["n"]) == \
        EXPECTED["clean_baseline_false_anchor"]


def test_base_rate_and_coverage_are_always_reported(tmp_path):
    report, payload = run(build(tmp_path))
    reported = codes(report, "INFO")
    assert "BASE_RATE" in reported          # collision-review R9: publish it
    assert "COVERAGE" in reported           # collision-review R3: publish blindness
    assert "PAIR" in reported               # collision-review R11: quote the pair
    assert payload["coverage"]["n"] == EXPECTED["valid_cells"]
    appendix = next(f for f in report.findings if f["code"] == "EXCLUSIONS")
    assert "INJECTION_UNVERIFIED 1" in appendix["message"]


def test_o4_is_scored_on_the_mapping_surface_only(tmp_path):
    """SPEC v0.2.1 section 10.3: the anchored-FLAGS surface is excluded for O4, so an
    anchored O4 flag must not lift the union."""
    def anchor_every_o4(sub):
        for task in TASKS:
            for label in LABELS:
                path = sub / "traces" / task / "O4" / label / "runresult.json"
                _write(path, _run_result(task, "O4", label,
                                         flags="the draft still says 41.7 and 47.1"))

    report, payload = run(build(tmp_path, corpus_edit=anchor_every_o4))
    assert not report.failed, report.render()
    assert payload["recomputed"]["flags_anchored"] == EXPECTED["flags_anchored"][0]
    assert payload["recomputed"]["union"] == EXPECTED["union"][0]


def test_json_output_carries_findings_and_exit_status(tmp_path, capsys):
    sub = build(tmp_path)
    status = VALIDATOR.main([str(sub), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert status == 0
    assert payload["exit"] == 0 and payload["verified"] is True
    assert all(set(f) == {"level", "code", "message"} for f in payload["findings"])


def test_cli_exits_non_zero_on_a_defective_submission(tmp_path, capsys):
    sub = build(tmp_path, manifest_edit=lambda m: m.pop("provenance"))
    assert VALIDATOR.main([str(sub)]) == 1
    assert "REJECTED" in capsys.readouterr().out


def test_a_missing_submission_directory_fails_cleanly(tmp_path, capsys):
    assert VALIDATOR.main([str(tmp_path / "nope")]) == 1
    assert "SUBMISSION" in capsys.readouterr().out


# --- defect classes --------------------------------------------------------------

def test_missing_cell_is_a_finding(tmp_path):
    def drop(sub):
        (sub / "traces" / "T3" / "O2" / "r4" / "runresult.json").unlink()

    report, payload = run(build(tmp_path, corpus_edit=drop))
    assert "CELL_MISSING" in codes(report)
    assert payload["verified"] is False


def test_missing_baseline_is_a_finding(tmp_path):
    def drop(sub):
        (sub / "traces" / "T2" / "baseline" / "r1"
         / "baseline-runresult.json").unlink()

    report, _ = run(build(tmp_path, corpus_edit=drop))
    assert "BASELINE_MISSING" in codes(report)


def test_a_trace_that_is_not_schema_v1_is_a_finding(tmp_path):
    def bump(sub):
        _write(sub / "traces" / "T1" / "O5" / "r2" / "runresult.json",
               _run_result("T1", "O5", "r2", schema_version=2))

    report, _ = run(build(tmp_path, corpus_edit=bump))
    assert "CELL_TRACE" in codes(report)


def test_a_malformed_trace_is_a_finding(tmp_path):
    def corrupt(sub):
        payload = _run_result("T4", "O1", "r3")
        # seq must strictly increase; Trace.add rejects this on parse.
        payload["trace"]["events"][1]["seq"] = 1
        _write(sub / "traces" / "T4" / "O1" / "r3" / "runresult.json", payload)

    report, _ = run(build(tmp_path, corpus_edit=corrupt))
    assert "CELL_TRACE" in codes(report)


def test_an_unknown_event_kind_is_a_finding(tmp_path):
    def corrupt(sub):
        payload = _run_result("T4", "O2", "r3")
        payload["trace"]["events"][1]["kind"] = "telepathy"
        _write(sub / "traces" / "T4" / "O2" / "r3" / "runresult.json", payload)

    report, _ = run(build(tmp_path, corpus_edit=corrupt))
    assert "CELL_TRACE" in codes(report)


def test_a_trace_that_disagrees_with_the_manifest_is_a_finding(tmp_path):
    def relabel(sub):
        payload = _run_result("T1", "O2", "r1")
        payload["trace"]["framework"] = "someotherframework"
        _write(sub / "traces" / "T1" / "O2" / "r1" / "runresult.json", payload)

    report, _ = run(build(tmp_path, corpus_edit=relabel))
    assert "TRACE_IDENTITY" in codes(report)


@pytest.mark.parametrize("key", ["wave1_mapping", "flags_anchored", "union",
                                 "reacted", "recovered", "strict_floor",
                                 "clean_baseline_false_anchor"])
def test_a_claimed_number_off_by_one_cell_is_a_finding(tmp_path, key):
    def off_by_one(manifest):
        counter = manifest["claimed"][key]
        counter["hits"] += 1 if counter["hits"] < counter["n"] else -1

    report, payload = run(build(tmp_path, manifest_edit=off_by_one))
    assert "RECOMPUTE" in codes(report)
    assert payload["verified"] is False


def test_a_claimed_valid_cell_count_that_ignores_an_exclusion_is_a_finding(tmp_path):
    def inflate(manifest):
        manifest["claimed"]["valid_cells"] = 150

    report, _ = run(build(tmp_path, manifest_edit=inflate))
    assert "RECOMPUTE" in codes(report)


def test_an_invalid_exclusion_class_is_a_finding(tmp_path):
    def bad_code(manifest):
        manifest["exclusions"][0]["code"] = "MODEL_WAS_TIRED"

    report, _ = run(build(tmp_path, manifest_edit=bad_code))
    assert "EXCLUSION_CLASS" in codes(report)


def test_an_exclusion_for_a_cell_outside_the_matrix_is_a_finding(tmp_path):
    def bad_cell(manifest):
        manifest["exclusions"].append({"task": "T9", "operator": "O1",
                                       "replicate": "r1", "code": "RUN_ERROR",
                                       "note": "no such cell"})

    report, _ = run(build(tmp_path, manifest_edit=bad_cell))
    assert "EXCLUSION_CLASS" in codes(report)


def test_an_exclusion_without_a_note_is_a_finding(tmp_path):
    def strip_note(manifest):
        manifest["exclusions"][0].pop("note")

    report, _ = run(build(tmp_path, manifest_edit=strip_note))
    assert "EXCLUSION_CLASS" in codes(report)


def test_an_undeclared_exclusion_is_a_finding(tmp_path):
    """A cell that recomputes as excluded but is not itemized was silently dropped."""
    def stop_itemizing(manifest):
        manifest["exclusions"] = []
        manifest["claimed"]["valid_cells"] = 149

    report, _ = run(build(tmp_path, manifest_edit=stop_itemizing))
    assert "EXCLUSION_UNDECLARED" in codes(report)


def test_a_declared_exclusion_that_recomputes_as_scoreable_is_a_finding(tmp_path):
    def over_declare(manifest):
        manifest["exclusions"].append({"task": "T3", "operator": "O5",
                                       "replicate": "r2", "code": "RUN_ERROR",
                                       "note": "claimed, but the trace is clean"})

    report, _ = run(build(tmp_path, manifest_edit=over_declare))
    assert "EXCLUSION_PRECEDENCE" in codes(report)


def test_exclusion_precedence_run_error_outranks_injection_unverified(tmp_path):
    """SPEC section 3: a cell qualifying for both is recorded under RUN_ERROR. The
    validator recomputes the code rather than trusting the manifest."""
    def erroring_cell(sub):
        _write(sub / "traces" / "T2" / "O1" / "r1" / "runresult.json",
               _run_result("T2", "O1", "r1", injection_verified=False,
                           error="HTTP 429 after one retry"))

    def mis_declare(manifest):
        manifest["exclusions"].append({"task": "T2", "operator": "O1",
                                       "replicate": "r1",
                                       "code": "INJECTION_UNVERIFIED",
                                       "note": "probe never fired"})
        manifest["claimed"]["valid_cells"] = 148
        for key in ("wave1_mapping", "flags_anchored", "union", "reacted",
                    "recovered", "strict_floor"):
            manifest["claimed"][key]["n"] = 148
        manifest["claimed"]["recovered"]["hits"] = 148

    report, _ = run(build(tmp_path, manifest_edit=mis_declare,
                          corpus_edit=erroring_cell))
    messages = [f["message"] for f in report.findings if f["code"] ==
                "EXCLUSION_PRECEDENCE"]
    assert messages and "RUN_ERROR" in messages[0]


def test_a_quarantined_exclusion_must_ship_its_trace(tmp_path):
    def drop_the_trace(sub):
        (sub / "traces" / UNVERIFIED_CELL[0] / UNVERIFIED_CELL[1]
         / UNVERIFIED_CELL[2] / "runresult.json").unlink()

    report, _ = run(build(tmp_path, corpus_edit=drop_the_trace))
    assert "EXCLUSION_EVIDENCE" in codes(report)


def test_a_baseline_fail_exclusion_is_checked_against_the_baseline(tmp_path):
    """BASELINE_FAIL is the one code that may ship no faulted trace -- but only when
    the baseline it names actually failed."""
    def drop_the_trace(sub):
        (sub / "traces" / "T4" / "O3" / "r2" / "runresult.json").unlink()

    def declare(manifest):
        manifest["exclusions"].append({"task": "T4", "operator": "O3",
                                       "replicate": "r2", "code": "BASELINE_FAIL",
                                       "note": "the shared baseline failed"})

    report, _ = run(build(tmp_path, manifest_edit=declare,
                          corpus_edit=drop_the_trace))
    assert "EXCLUSION_PRECEDENCE" in codes(report)


def test_a_baseline_fail_exclusion_passes_when_the_baseline_really_failed(tmp_path):
    def fail_the_baseline(sub):
        _write(sub / "traces" / "T4" / "baseline" / "r2" / "baseline-runresult.json",
               _run_result("T4", None, "r2", task_passed=False, injection_seq=None,
                           injection_verified=False))
        (sub / "traces" / "T4" / "O3" / "r2" / "runresult.json").unlink()

    def declare(manifest):
        manifest["exclusions"].append({"task": "T4", "operator": "O3",
                                       "replicate": "r2", "code": "BASELINE_FAIL",
                                       "note": "the shared baseline failed the task"})
        # Every other T4/r2 cell now excludes on the same dead baseline.
        for operator in OPERATORS:
            if operator == "O3":
                continue
            manifest["exclusions"].append({"task": "T4", "operator": operator,
                                           "replicate": "r2",
                                           "code": "BASELINE_FAIL",
                                           "note": "shares the dead T4/r2 baseline"})
        manifest["claimed"]["valid_cells"] = 143
        for key in ("wave1_mapping", "flags_anchored", "union", "reacted",
                    "recovered", "strict_floor"):
            manifest["claimed"][key]["n"] = 143
        manifest["claimed"]["recovered"]["hits"] = 143

    report, payload = run(build(tmp_path, manifest_edit=declare,
                                corpus_edit=fail_the_baseline))
    assert not report.failed, report.render()
    assert payload["recomputed"]["valid"] == 143


# --- manifest discipline ---------------------------------------------------------

def test_a_manifest_that_calls_replicates_seeds_is_rejected(tmp_path):
    def rename(manifest):
        manifest["seeds"] = manifest.pop("replicate_labels")
        manifest["replicate_labels"] = list(LABELS)

    report, _ = run(build(tmp_path, manifest_edit=rename))
    assert "REPLICATES" in codes(report)


def test_fewer_than_five_replicates_is_a_finding(tmp_path):
    def shrink(manifest):
        manifest["replicate_labels"] = ["r1", "r2", "r3"]

    report, _ = run(build(tmp_path, manifest_edit=shrink))
    assert "REPLICATES" in codes(report)


def test_provenance_must_be_third_party(tmp_path):
    def relabel(manifest):
        manifest["provenance"] = "author-run"

    report, _ = run(build(tmp_path, manifest_edit=relabel))
    assert "PROVENANCE" in codes(report)


def test_a_version_range_is_not_a_pin(tmp_path):
    def unpin(manifest):
        manifest["dependency_pins"]["exampleframework-openai"] = ">=0.9,<1.0"

    report, _ = run(build(tmp_path, manifest_edit=unpin))
    assert "PINS" in codes(report)


def test_an_untagged_spec_version_is_a_finding(tmp_path):
    def drift(manifest):
        manifest["spec_version"] = "v0.0.9"

    report, _ = run(build(tmp_path, manifest_edit=drift))
    assert "SPEC_VERSION" in codes(report)


def test_a_wave1_mapping_row_may_not_claim_a_flags_surface(tmp_path):
    def downgrade(manifest):
        manifest["protocol"] = "wave1-mapping"

    report, _ = run(build(tmp_path, manifest_edit=downgrade))
    assert "CLAIMED" in codes(report)


def test_a_wave1_mapping_row_validates_on_the_mapping_surface_alone(tmp_path):
    def downgrade(manifest):
        manifest["protocol"] = "wave1-mapping"
        for key in ("flags_anchored", "union"):
            manifest["claimed"].pop(key)

    report, _ = run(build(tmp_path, manifest_edit=downgrade))
    assert not report.failed, report.render()


def test_a_missing_manifest_is_a_finding(tmp_path):
    def drop(sub):
        (sub / "manifest.json").unlink()

    report, _ = run(build(tmp_path, corpus_edit=drop))
    assert "MANIFEST_PARSE" in codes(report)


def test_unparseable_manifest_json_is_a_finding(tmp_path):
    def corrupt(sub):
        (sub / "manifest.json").write_text("{not json")

    report, _ = run(build(tmp_path, corpus_edit=corrupt))
    assert "MANIFEST_PARSE" in codes(report)


def test_a_manifest_with_the_wrong_schema_string_is_a_finding(tmp_path):
    def rename(manifest):
        manifest["schema"] = "sabot-submission/99"

    report, _ = run(build(tmp_path, manifest_edit=rename))
    # The wrong schema string stops every other manifest check dead.
    assert codes(report)[0] == "MANIFEST_SCHEMA"
    assert "RECOMPUTE" not in codes(report)


def test_a_structurally_broken_manifest_aborts_before_scoring(tmp_path):
    def wreck(manifest):
        manifest.pop("framework")

    report, payload = run(build(tmp_path, manifest_edit=wreck))
    assert "ABORT" in codes(report)
    assert payload["recomputed"] is None


def test_a_missing_mapping_document_is_a_finding(tmp_path):
    def drop(sub):
        (sub / "mapping.md").unlink()

    report, _ = run(build(tmp_path, corpus_edit=drop))
    assert "MAPPING_DOC" in codes(report)


def test_a_mapping_document_without_an_act_table_is_a_finding(tmp_path):
    def gut(sub):
        (sub / "mapping.md").write_text("# Mapping\n\nWe reviewed it. Trust us.\n")

    report, _ = run(build(tmp_path, corpus_edit=gut))
    assert "MAPPING_DOC" in codes(report)


# --- carve-outs and external corpora ---------------------------------------------

def test_a_declared_carve_out_leaves_the_matrix(tmp_path):
    """The SPEC 10.6 pattern: carved cells are never run and never counted."""
    def carve(manifest):
        manifest["carve_outs"] = [{
            "operator": "O6", "spec_ref": "SPEC 10.6",
            "reason": "O6 lands after the team run completes; no component sees it"}]
        manifest["exclusions"] = []
        manifest["claimed"]["valid_cells"] = 125
        for key in ("wave1_mapping", "flags_anchored", "union", "reacted",
                    "recovered", "strict_floor"):
            manifest["claimed"][key]["n"] = 125
        manifest["claimed"]["recovered"]["hits"] = 125

    report, payload = run(build(tmp_path, manifest_edit=carve))
    assert not report.failed, report.render()
    assert payload["recomputed"]["valid"] == 125


def test_a_carve_out_without_a_reason_is_a_finding(tmp_path):
    def carve(manifest):
        manifest["carve_outs"] = [{"operator": "O6"}]

    report, _ = run(build(tmp_path, manifest_edit=carve))
    assert "CARVE_OUT" in codes(report)


def test_an_external_corpus_is_reported_unverified_not_scored(tmp_path):
    def externalize(manifest):
        manifest["traces"] = {
            "tarball_url": "https://example.org/releases/traces.tar.gz",
            "sha256": "a" * 64}

    def drop_corpus(sub):
        for path in sorted((sub / "traces").rglob("*.json"), reverse=True):
            path.unlink()

    report, payload = run(build(tmp_path, manifest_edit=externalize,
                                corpus_edit=drop_corpus))
    assert not report.failed, report.render()
    assert "EXTERNAL" in codes(report, "INFO")
    assert payload["verified"] is False      # CI validates only what is in-repo


def test_an_external_corpus_needs_a_real_digest(tmp_path):
    def externalize(manifest):
        manifest["traces"] = {"tarball_url": "https://example.org/traces.tar.gz",
                              "sha256": "not-a-digest"}

    report, _ = run(build(tmp_path, manifest_edit=externalize))
    assert "TRACES" in codes(report)


def test_an_absent_corpus_with_no_external_reference_is_a_finding(tmp_path):
    def drop_corpus(sub):
        for path in sorted((sub / "traces").rglob("*.json"), reverse=True):
            path.unlink()

    report, _ = run(build(tmp_path, corpus_edit=drop_corpus))
    assert "TRACES" in codes(report)


# --- the shipped template --------------------------------------------------------

def test_the_shipped_template_fails_loudly(tmp_path):
    """submissions/TEMPLATE is a skeleton, not a row: it must never validate clean,
    and it must say why."""
    template = ROOT.parent / "submissions" / "TEMPLATE"
    if not template.is_dir():
        pytest.skip("submissions/TEMPLATE not present in this checkout")
    report, payload = run(template)
    assert report.failed
    assert payload["verified"] is False
    assert "TRACES" in codes(report)
