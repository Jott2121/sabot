#!/usr/bin/env python
"""Soft-tier judge batch (SPEC section 6). Core-venv script — no framework imports.

Judged set: valid faulted cells (excluded == null) with detected_hard == false; a
hard-detected cell is already inside the soft-notice union, so judging it cannot move
any published number. assert_sandboxed() runs before EVERY batch (Phase-3 ledger note).
Double-judge: every 5th cell of the lexicographically-sorted judged set (index % 5 == 0)
re-judged with prompt_variant=1 — a deterministic, pre-registered 20% with no RNG.
JudgeParseError after judge_cell's built-in retry = a counted, published judge-exclusion
(never a coerced verdict). $0 marginal (claude -p on Max)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.judge.notes import ground_truth_note
from sabot.judge.rubric import JudgeParseError, cohens_kappa
from sabot.judge.runner import assert_sandboxed, judge_cell
from sabot.serde import run_result_from_json


def _eligible(runs_dir: Path) -> list[Path]:
    cells = []
    for vfile in sorted(runs_dir.rglob("cellverdict.json")):
        v = json.loads(vfile.read_text())
        if v["excluded"] is None and not v["detected_hard"]:
            cells.append(vfile.parent)
    return cells


def _judge_one(cell_dir: Path, tasks_dir: Path, variant: int) -> bool | None:
    """Returns noticed, or None on a judge-exclusion. Writes the artifact either way."""
    suffix = "" if variant == 0 else f"-variant{variant}"
    out = cell_dir / f"judgeverdict{suffix}.json"
    exc = cell_dir / f"judge-excluded{suffix}.json"
    if out.exists():
        return json.loads(out.read_text())["noticed"]
    if exc.exists():
        return None
    r = run_result_from_json((cell_dir / "runresult.json").read_text())
    note = ground_truth_note(r.trace.task, r.trace.operator, tasks_dir)
    try:
        v = judge_cell(r.trace, note, prompt_variant=variant)
    except JudgeParseError as e:
        exc.write_text(json.dumps({"reason": "JudgeParseError", "detail": str(e)[:400]}))
        return None
    out.write_text(json.dumps({"noticed": v.noticed,
                               "by_which_component": v.by_which_component,
                               "evidence_quote": v.evidence_quote, "raw": v.raw,
                               "prompt_variant": variant}, sort_keys=True))
    return v.noticed


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--batch-size", type=int, default=25)
    a = p.parse_args(argv)
    runs_dir, tasks_dir = Path(a.runs_dir), Path(a.tasks_dir)
    cells = _eligible(runs_dir)
    doubles = set(cells[::5])                      # pre-registered 20% rule
    pairs: list[tuple[bool, bool]] = []
    todo = [(c, 0) for c in cells] + [(c, 1) for c in cells if c in doubles]
    for i in range(0, len(todo), a.batch_size):
        assert_sandboxed()
        for cell_dir, variant in todo[i:i + a.batch_size]:
            noticed = _judge_one(cell_dir, tasks_dir, variant)
            print(f"{cell_dir.relative_to(runs_dir)} v{variant}: noticed={noticed}",
                  flush=True)
    # counted from disk, not a loop counter, so a resumed invocation still reports the
    # TOTAL exclusions (the test's resume assertion depends on this). Primary-pass
    # exclusions only: a variant-1 parse failure just drops its kappa pair below.
    exclusions = len(list(runs_dir.rglob("judge-excluded.json")))
    for c in sorted(doubles):
        v0, v1 = c / "judgeverdict.json", c / "judgeverdict-variant1.json"
        if v0.exists() and v1.exists():
            pairs.append((json.loads(v0.read_text())["noticed"],
                          json.loads(v1.read_text())["noticed"]))
    kappa = (cohens_kappa([x for x, _ in pairs], [y for _, y in pairs])
             if len(pairs) >= 2 else None)
    (runs_dir / "judge-kappa.json").write_text(json.dumps(
        {"pairs": len(pairs), "kappa": kappa,
         "low_confidence": (kappa is None or kappa < 0.7),
         "judge_exclusions": exclusions}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
