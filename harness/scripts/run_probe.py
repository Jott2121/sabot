#!/usr/bin/env python
"""Wave-2 anomaly-first probe driver — run with the target framework's venv python
(.venv-crewai or .venv-autogen). Modeled on scripts/run_matrix.py (baseline caching,
resume, retry-once, ledger, cap breaker) but scoped to the pre-registered probe cells
(docs/probe-anomaly-first-2026-07-23.md) and writing ONLY to its own out-dir — the
frozen wave-1 dataset under runs/matrix/ is never touched.

Probe scope: guardrail config only, T1/T2/T3/T5 x O1/O3 x wave-1 seeds. Baselines are
RE-RUN under the probe prompts (the pipeline changed, so wave-1 baselines cannot vouch
for probe validity). Cells score through the frozen run_cell/score path — the wave-1
act mapping, unchanged — and the FLAGS surface is adjudicated post-hoc by
scripts/score_probe.py from the recorded traces."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.adapters.operator_specs import SPECS
from sabot.matrix import CellKey, run_profile, spent_usd
from sabot.runner import Cell, run_cell
from sabot.score import score
from sabot.serde import cell_verdict_to_json, run_result_from_json, run_result_to_json

PROBE_TASKS = ("T1", "T2", "T3", "T5")
PROBE_OPERATORS = ("O1", "O3")
PROBE_CONFIG = "guardrail"
PROBE_CAP_USD = 25.0        # probe-local circuit breaker, far under the $500 project cap


def _load_key() -> None:
    key_file = Path.home() / ".config" / "oracle-gate" / "openai.key"
    os.environ.setdefault("OPENAI_API_KEY", key_file.read_text().strip())


def _adapter(framework: str, tasks_dir: Path):
    if framework == "crewai":
        from sabot.adapters.probe_crewai import ProbeCrewAIAdapter
        return ProbeCrewAIAdapter(tasks_dir=tasks_dir)
    if framework == "autogen":
        from sabot.adapters.probe_autogen import ProbeAutoGenAdapter
        return ProbeAutoGenAdapter(tasks_dir=tasks_dir)
    raise SystemExit(f"framework outside probe scope: {framework}")


def _run_retry_once(adapter, cell: Cell):
    r = adapter.run(cell)
    if r.error is None:
        return r, 0
    return adapter.run(cell), 1


def _check_cap(out: Path) -> None:
    counts: dict[str, int] = {}
    for lp in out.glob("ledger-*.jsonl"):
        for line in lp.read_text().splitlines():
            d = json.loads(line)
            counts[d["profile"]] = counts.get(d["profile"], 0) + d["runs"]
    usd = spent_usd(counts)
    if usd >= PROBE_CAP_USD:
        raise SystemExit(f"PROBE CAP: projected spend ${usd:.2f} >= ${PROBE_CAP_USD:.0f} — "
                         "stopping before the next paid run")


def _ledger(out: Path, framework: str, entry: dict) -> None:
    line = json.dumps({"excluded": None, "detected_hard": False, "recovered": False,
                       "retried": 0, "skipped": None, **entry}, sort_keys=True)
    with (out / f"ledger-{framework}.jsonl").open("a") as f:
        f.write(line + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--framework", required=True, choices=("crewai", "autogen"))
    p.add_argument("--seeds-file", required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--out-dir", default="runs/probe-anomaly")
    a = p.parse_args(argv)
    _load_key()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = json.loads(Path(a.seeds_file).read_text())["seeds"]
    adapter = _adapter(a.framework, Path(a.tasks_dir))
    profile = run_profile(a.framework, PROBE_CONFIG)

    for task in PROBE_TASKS:
        for seed in seeds:
            bkey = CellKey(a.framework, PROBE_CONFIG, task, None, seed)
            bdir = out / bkey.relpath()
            bdir.mkdir(parents=True, exist_ok=True)
            bfile = bdir / "baseline-runresult.json"
            if bfile.exists():
                baseline = run_result_from_json(bfile.read_text())
            else:
                _check_cap(out)
                baseline, retried = _run_retry_once(
                    adapter, Cell(a.framework, task, PROBE_CONFIG, None, None, seed))
                bfile.write_text(run_result_to_json(baseline))
                _ledger(out, a.framework,
                        {"profile": profile, "runs": 1 + retried,
                         "cell": bkey.relpath(), "retried": retried})
            baseline_dead = baseline.error is not None or not baseline.task_passed
            for op in PROBE_OPERATORS:
                key = CellKey(a.framework, PROBE_CONFIG, task, op, seed)
                cdir = out / key.relpath()
                cdir.mkdir(parents=True, exist_ok=True)
                vfile = cdir / "cellverdict.json"
                if vfile.exists():
                    continue                      # resume
                if baseline_dead:
                    verdict = score(trace=baseline.trace, injection_seq=0,
                                    baseline_passed=baseline.task_passed,
                                    task_passed=False, injection_verified=False,
                                    run_error=baseline.error is not None)
                    vfile.write_text(cell_verdict_to_json(verdict))
                    _ledger(out, a.framework,
                            {"profile": profile, "runs": 0, "cell": key.relpath(),
                             "excluded": verdict.excluded, "skipped": "baseline_excluded"})
                    continue
                _check_cap(out)
                cell = Cell(a.framework, task, PROBE_CONFIG, op, SPECS[(task, op)], seed)
                faulted, retried = _run_retry_once(adapter, cell)
                (cdir / "runresult.json").write_text(run_result_to_json(faulted))
                verdict = run_cell(adapter, cell, faulted, baseline)
                vfile.write_text(cell_verdict_to_json(verdict))
                _ledger(out, a.framework,
                        {"profile": profile, "runs": 1 + retried, "cell": key.relpath(),
                         "excluded": verdict.excluded,
                         "detected_hard": verdict.detected_hard,
                         "recovered": verdict.recovered, "retried": retried})
                print(f"{key.relpath()}: excluded={verdict.excluded} "
                      f"hard={verdict.detected_hard} recovered={verdict.recovered}",
                      flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
