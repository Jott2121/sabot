#!/usr/bin/env python
"""Wave-2 soft-tier judge batch (SPEC section 6, unchanged protocol; v0.2.0 headline
context). Core-venv script — no framework imports.

Identical to scripts/run_judge.py except eligibility: wave-2's hard tier is the UNION
(frozen mapping OR anchored FLAGS, SPEC 10.5), so the published skip rule — "a
hard-detected cell is already inside the soft-notice union, so judging it cannot move
any published number" — extends to union-detected cells. Judged set = valid faulted
cells with union == false. The deterministic every-5th double-judge and the per-batch
assert_sandboxed() discipline are inherited unchanged."""
from __future__ import annotations
import argparse, importlib.util, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.wave2 import scan_trace_flags_v2

_spec = importlib.util.spec_from_file_location(
    "run_judge", Path(__file__).resolve().parent / "run_judge.py")
run_judge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_judge)


def _eligible_union_false(runs_dir: Path) -> list[Path]:
    cells = []
    for vfile in sorted(runs_dir.rglob("cellverdict.json")):
        v = json.loads(vfile.read_text())
        if v["excluded"] is not None or v["detected_hard"]:
            continue
        rr_file = vfile.parent / "runresult.json"
        if not rr_file.exists():
            continue
        rr = json.loads(rr_file.read_text())
        parts = vfile.parent.relative_to(runs_dir).parts   # fw/config/task/op/seedN
        task, op = parts[2], parts[3]
        scan = scan_trace_flags_v2(rr["trace"], task, op, rr["injection_seq"] or 0)
        if not scan["anchored"]:
            cells.append(vfile.parent)
    return cells


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--batch-size", type=int, default=25)
    a = p.parse_args(argv)
    runs_dir, tasks_dir = Path(a.runs_dir), Path(a.tasks_dir)
    cells = _eligible_union_false(runs_dir)
    print(f"judged set (union==false): {len(cells)} cells", flush=True)
    doubles = set(cells[::5])
    pairs: list[tuple[bool, bool]] = []
    todo = [(c, 0) for c in cells] + [(c, 1) for c in cells if c in doubles]
    for i in range(0, len(todo), a.batch_size):
        run_judge.assert_sandboxed()
        for cell_dir, variant in todo[i:i + a.batch_size]:
            noticed = run_judge._judge_one(cell_dir, tasks_dir, variant)
            print(f"{cell_dir.relative_to(runs_dir)} v{variant}: noticed={noticed}",
                  flush=True)
    exclusions = len(list(runs_dir.rglob("judge-excluded.json")))
    for c in sorted(doubles):
        v0, v1 = c / "judgeverdict.json", c / "judgeverdict-variant1.json"
        if v0.exists() and v1.exists():
            pairs.append((json.loads(v0.read_text())["noticed"],
                          json.loads(v1.read_text())["noticed"]))
    kappa = (run_judge.cohens_kappa([x for x, _ in pairs], [y for _, y in pairs])
             if len(pairs) >= 2 else None)
    (runs_dir / "judge-kappa.json").write_text(json.dumps(
        {"pairs": len(pairs), "kappa": kappa,
         "low_confidence": (kappa is None or kappa < 0.7),
         "judge_exclusions": exclusions}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
