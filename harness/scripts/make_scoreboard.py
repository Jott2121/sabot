#!/usr/bin/env python
"""Walk runs/matrix, build CellRecords, write RESULTS.md (staged PRIVATE until reveal)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.scoreboard import CellRecord, aggregate, render_markdown


def _records(runs_dir: Path) -> list[CellRecord]:
    recs = []
    for vfile in sorted(runs_dir.rglob("cellverdict.json")):
        parts = vfile.parent.relative_to(runs_dir).parts
        fw, config, task, op, seed = parts
        if op == "baseline":
            continue
        v = json.loads(vfile.read_text())
        jv = vfile.parent / "judgeverdict.json"
        jx = vfile.parent / "judge-excluded.json"
        recs.append(CellRecord(
            framework=fw, config=config, task=task, operator=op,
            seed=int(seed.removeprefix("seed")), excluded=v["excluded"],
            detected_hard=v["detected_hard"], reacted=v["reacted"],
            recovered=v["recovered"],
            judge_noticed=json.loads(jv.read_text())["noticed"] if jv.exists() else None,
            judge_excluded=jx.exists()))
    return recs


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs-dir", required=True)
    p.add_argument("--out", default="RESULTS.md")
    a = p.parse_args(argv)
    runs_dir = Path(a.runs_dir)
    kfile = runs_dir / "judge-kappa.json"
    kappa = json.loads(kfile.read_text()) if kfile.exists() else None
    md = render_markdown(aggregate(_records(runs_dir)), kappa)
    Path(a.out).write_text(md)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
