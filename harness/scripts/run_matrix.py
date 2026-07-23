#!/usr/bin/env python
"""Phase-4 matrix driver — one framework per process, run with THAT framework's venv
python (.venv-<framework>/bin/python). In-process adapter reuse caches every no-fault
baseline per (framework, config, task, seed); naive per-cell looping would re-pay ~900
baseline runs (the Phase-3 ledger's cost landmine). scripts/run_cell.py's published CLI
contract is deliberately untouched.

Three drivers (one per framework) may run concurrently against one --out-dir: each
appends only to its own ledger-<framework>.jsonl; the cap check reads all ledgers."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.adapters.operator_specs import SPECS
from sabot.matrix import CONFIGS, HARD_CAP_USD, OPERATORS, TASKS, CellKey, run_profile, spent_usd
from sabot.runner import Cell, run_cell
from sabot.score import score
from sabot.serde import cell_verdict_to_json, run_result_from_json, run_result_to_json


def _load_key() -> None:
    key_file = Path.home() / ".config" / "oracle-gate" / "openai.key"
    os.environ.setdefault("OPENAI_API_KEY", key_file.read_text().strip())


def _adapter(framework: str, tasks_dir: Path):
    if framework == "langgraph":
        from sabot.adapters.langgraph_adapter import LangGraphAdapter
        return LangGraphAdapter(tasks_dir=tasks_dir)
    if framework == "crewai":
        from sabot.adapters.crewai_adapter import CrewAIAdapter
        return CrewAIAdapter(tasks_dir=tasks_dir)
    if framework == "autogen":
        from sabot.adapters.autogen_adapter import AutoGenAdapter
        return AutoGenAdapter(tasks_dir=tasks_dir)
    raise SystemExit(f"unknown framework: {framework}")


def _run_retry_once(adapter, cell: Cell):
    """SPEC section 3: RUN_ERROR retried once, then excluded. CrewAI guardrail exhaustion
    is a scored escalate inside the adapter (error=None) and never reaches this path."""
    r = adapter.run(cell)
    if r.error is None:
        return r, 0
    return adapter.run(cell), 1


def _output_chars(result) -> int:
    return sum(len(json.dumps(e.payload, sort_keys=True)) for e in result.trace.events)


def _check_cap(out: Path) -> None:
    counts: dict[str, int] = {}
    for lp in out.glob("ledger-*.jsonl"):
        for line in lp.read_text().splitlines():
            d = json.loads(line)
            counts[d["profile"]] = counts.get(d["profile"], 0) + d["runs"]
    usd = spent_usd(counts)
    if usd >= HARD_CAP_USD:
        raise SystemExit(f"HARD CAP: projected spend ${usd:.2f} >= ${HARD_CAP_USD:.0f} — "
                         "stopping before the next paid run")


def _ledger(out: Path, framework: str, entry: dict) -> None:
    line = json.dumps({"excluded": None, "detected_hard": False, "recovered": False,
                       "retried": 0, "output_chars": 0, "skipped": None, **entry},
                      sort_keys=True)
    with (out / f"ledger-{framework}.jsonl").open("a") as f:
        f.write(line + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--framework", required=True)
    p.add_argument("--seeds-file", required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--out-dir", default="runs/matrix")
    a = p.parse_args(argv)
    _load_key()
    tasks_dir = Path(a.tasks_dir)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = json.loads(Path(a.seeds_file).read_text())["seeds"]
    adapter = _adapter(a.framework, tasks_dir)
    profile_of = {c: run_profile(a.framework, c) for c in CONFIGS}

    for config in CONFIGS:
        for task in TASKS:
            for seed in seeds:
                bkey = CellKey(a.framework, config, task, None, seed)
                bdir = out / bkey.relpath()
                bdir.mkdir(parents=True, exist_ok=True)
                bfile = bdir / "baseline-runresult.json"
                if bfile.exists():
                    baseline = run_result_from_json(bfile.read_text())
                else:
                    _check_cap(out)
                    baseline, retried = _run_retry_once(
                        adapter, Cell(a.framework, task, config, None, None, seed))
                    bfile.write_text(run_result_to_json(baseline))
                    _ledger(out, a.framework,
                            {"profile": profile_of[config], "runs": 1 + retried,
                             "cell": bkey.relpath(), "retried": retried,
                             "output_chars": _output_chars(baseline)})
                baseline_dead = baseline.error is not None or not baseline.task_passed
                for op in OPERATORS:
                    key = CellKey(a.framework, config, task, op, seed)
                    cdir = out / key.relpath()
                    cdir.mkdir(parents=True, exist_ok=True)
                    vfile = cdir / "cellverdict.json"
                    if vfile.exists():
                        continue                      # resume
                    if baseline_dead:
                        # exclusion is decided by the shared baseline; do not pay for
                        # six faulted runs that score() must exclude anyway
                        verdict = score(trace=baseline.trace, injection_seq=0,
                                        baseline_passed=baseline.task_passed,
                                        task_passed=False, injection_verified=False,
                                        run_error=baseline.error is not None)
                        vfile.write_text(cell_verdict_to_json(verdict))
                        _ledger(out, a.framework,
                                {"profile": profile_of[config], "runs": 0,
                                 "cell": key.relpath(), "excluded": verdict.excluded,
                                 "skipped": "baseline_excluded"})
                        continue
                    _check_cap(out)
                    cell = Cell(a.framework, task, config, op, SPECS[(task, op)], seed)
                    faulted, retried = _run_retry_once(adapter, cell)
                    (cdir / "runresult.json").write_text(run_result_to_json(faulted))
                    verdict = run_cell(adapter, cell, faulted, baseline)
                    vfile.write_text(cell_verdict_to_json(verdict))
                    _ledger(out, a.framework,
                            {"profile": profile_of[config], "runs": 1 + retried,
                             "cell": key.relpath(), "excluded": verdict.excluded,
                             "detected_hard": verdict.detected_hard,
                             "recovered": verdict.recovered, "retried": retried,
                             "output_chars": _output_chars(faulted)})
                    print(f"{key.relpath()}: excluded={verdict.excluded} "
                          f"hard={verdict.detected_hard} recovered={verdict.recovered}",
                          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
