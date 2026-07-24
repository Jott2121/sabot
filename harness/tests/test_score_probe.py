"""Probe scorer: end-to-end over a synthetic probe out-dir + synthetic wave-1 matrix
dir — exclusion handling, flags adjudication from real serde artifacts, aggregation
arithmetic, and the union rule."""
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("score_probe", ROOT / "scripts" / "score_probe.py")
score_probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_spec and score_probe)


def _write(path: pathlib.Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def _cell(root, fw, task, op, seed):
    return root / fw / "guardrail" / task / op / f"seed{seed}"


def _runresult(events, injection_seq=2):
    return {"trace": {"run_id": "r", "framework": "crewai", "task": "T1",
                      "config": "guardrail", "operator": "O1", "seed": 11,
                      "schema_version": 1, "events": events},
            "task_passed": True, "injection_seq": injection_seq,
            "injection_verified": True, "error": None}


def _verdict(detected_hard=False, excluded=None):
    return {"detected_hard": detected_hard, "reacted": detected_hard,
            "recovered": True, "excluded": excluded, "acts": []}


def _msg(seq, text):
    return {"kind": "agent-msg", "agent": "reviewer", "seq": seq, "payload": {"text": text}}


def test_collect_and_aggregate(tmp_path):
    probe, matrix = tmp_path / "probe", tmp_path / "matrix"
    # seed 11: anchored flag, no wave1-mapping act; wave-1 cell was a miss
    _write(_cell(probe, "crewai", "T1", "O1", 11) / "cellverdict.json", _verdict(False))
    _write(_cell(probe, "crewai", "T1", "O1", 11) / "runresult.json",
           _runresult([_msg(5, "FLAGS: 74.1 vs 47.1\nVERDICT: APPROVE")]))
    _write(_cell(matrix, "crewai", "T1", "O1", 11) / "cellverdict.json", _verdict(False))
    # seed 12: wave1-mapping act fired, FLAGS said none; wave-1 cell was a hit
    _write(_cell(probe, "crewai", "T1", "O1", 12) / "cellverdict.json", _verdict(True))
    _write(_cell(probe, "crewai", "T1", "O1", 12) / "runresult.json",
           _runresult([_msg(5, "FLAGS: none\nVERDICT: REJECT - wrong value")]))
    _write(_cell(matrix, "crewai", "T1", "O1", 12) / "cellverdict.json", _verdict(True))
    # seed 13: excluded in the probe — must not enter any rate
    _write(_cell(probe, "crewai", "T1", "O1", 13) / "cellverdict.json",
           _verdict(False, excluded="BASELINE_FAIL"))
    # seed 14: never run — must be skipped entirely
    rows = score_probe.collect(probe, matrix, "crewai", [11, 12, 13, 14])
    assert len(rows) == 3
    by_seed = {r["seed"]: r for r in rows}
    assert by_seed[11]["flags_anchored"] is True
    assert by_seed[11]["wave1_mapping"] is False
    assert by_seed[11]["wave1_hard"] is False
    assert by_seed[12]["flags_anchored"] is False
    assert by_seed[12]["wave1_mapping"] is True
    assert by_seed[13]["excluded"] == "BASELINE_FAIL"

    groups = score_probe.aggregate(rows, lambda r: (r["framework"], r["operator"]))
    g = groups[("crewai", "O1")]
    assert g == {"valid": 2, "wave1_mapping": 1, "flags_anchored": 1, "union": 2,
                 "flags_noticed": 1, "wave1_valid": 2, "wave1_hard": 1}


def test_render_contains_rates_and_exclusions(tmp_path):
    probe, matrix = tmp_path / "probe", tmp_path / "matrix"
    _write(_cell(probe, "crewai", "T1", "O1", 11) / "cellverdict.json", _verdict(False))
    _write(_cell(probe, "crewai", "T1", "O1", 11) / "runresult.json",
           _runresult([_msg(5, "FLAGS: 74.1\nVERDICT: APPROVE")]))
    _write(_cell(probe, "crewai", "T1", "O3", 11) / "cellverdict.json",
           _verdict(False, excluded="RUN_ERROR"))
    rows = score_probe.collect(probe, matrix, "crewai", [11])
    md = score_probe.render(rows)
    assert "| crewai | O1 | 1 |" in md
    assert "100.0% (1/1)" in md          # union: anchored flag on the only valid cell
    assert "crewai/guardrail/T1/O3/seed11: RUN_ERROR" in md
    assert "n/a (0)" in md               # wave-1 comparator absent in the synthetic matrix


def test_missing_runresult_scores_no_flags(tmp_path):
    probe, matrix = tmp_path / "probe", tmp_path / "matrix"
    _write(_cell(probe, "crewai", "T2", "O3", 11) / "cellverdict.json", _verdict(True))
    rows = score_probe.collect(probe, matrix, "crewai", [11])
    assert rows[0]["flags_noticed"] is False and rows[0]["flags_anchored"] is False
