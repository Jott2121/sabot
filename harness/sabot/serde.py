"""JSON round-trip for RunResult and CellVerdict. Lives outside runner.py/score.py so
the frozen Phase-2 surfaces stay untouched; the Phase-4 matrix driver and run_cell.py
speak these files across venv/subprocess boundaries."""
from __future__ import annotations
import json
from sabot.acts import DetectionAct
from sabot.runner import RunResult
from sabot.score import CellVerdict
from sabot.trace import Trace


def run_result_to_json(r: RunResult) -> str:
    return json.dumps({
        "trace": json.loads(r.trace.to_json()),
        "task_passed": r.task_passed,
        "injection_seq": r.injection_seq,
        "injection_verified": r.injection_verified,
        "error": r.error,
    }, sort_keys=True)


def run_result_from_json(s: str) -> RunResult:
    d = json.loads(s)
    return RunResult(trace=Trace.from_json(json.dumps(d["trace"])),
                     task_passed=d["task_passed"], injection_seq=d["injection_seq"],
                     injection_verified=d["injection_verified"], error=d["error"])


def cell_verdict_to_json(v: CellVerdict) -> str:
    return json.dumps({
        "detected_hard": v.detected_hard, "reacted": v.reacted,
        "recovered": v.recovered, "excluded": v.excluded,
        "acts": [{"component": a.component, "act": a.act,
                  "reason": a.reason, "seq": a.seq} for a in v.acts],
    }, sort_keys=True)


def cell_verdict_from_json(s: str) -> CellVerdict:
    d = json.loads(s)
    return CellVerdict(detected_hard=d["detected_hard"], reacted=d["reacted"],
                       recovered=d["recovered"], excluded=d["excluded"],
                       acts=tuple(DetectionAct(**a) for a in d["acts"]))
