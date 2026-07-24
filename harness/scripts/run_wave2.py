#!/usr/bin/env python
"""Wave-2 matrix driver (SPEC v0.2.0 section 10) — run with the target framework's
venv python (.venv-langgraph / .venv-crewai / .venv-autogen). Modeled on
scripts/run_probe.py: baseline caching, resume via cellverdict-exists, retry-once,
ledger, and a margined circuit breaker SHARED across all three frameworks' ledgers
in the out-dir. Writes ONLY to its own out-dir — the frozen wave-1 dataset under
runs/matrix/ and the pilot's runs/probe-anomaly/ are never touched.

Scope (SPEC 10.6): both configs x T1-T5 x O1-O6 x the registered wave-2 seeds,
MINUS the pre-registered Magentic structural carve-out (autogen/guardrail x
O2/O3/O6) — carved cells are never run and never ledgered; they are not part of
the 825-cell matrix. Baselines are RE-RUN under v0.2 prompts (a changed pipeline
cannot borrow wave-1 baselines).

Cells score through the frozen run_cell/score path — the wave-1 act mapping,
unchanged (the `wave1_mapping` surface, SPEC 10.5); the FLAGS surface is
adjudicated post-hoc by scripts/score_wave2.py from the recorded traces.

BREAKER: $38 margined (the wave-2 wallet is $47; margined under-reads real by
~1.17x — SPEND.md dashboard reconcile). If the breaker trips, STOP AND SURFACE;
never raise it to finish."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.adapters.operator_specs import SPECS
from sabot.matrix import CellKey, run_profile, spent_usd
from sabot.runner import Cell, run_cell
from sabot.score import score
from sabot.serde import cell_verdict_to_json, run_result_from_json, run_result_to_json
from sabot.wave2 import is_carved_out

TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")
CONFIGS = ("default", "guardrail")
WAVE2_CAP_USD = 38.0        # margined breaker; wallet $47; stop-and-surface on trip


def _load_key() -> None:
    key_file = Path.home() / ".config" / "oracle-gate" / "openai.key"
    os.environ.setdefault("OPENAI_API_KEY", key_file.read_text().strip())


def _adapter(framework: str, tasks_dir: Path):
    if framework == "langgraph":
        from sabot.adapters.wave2_langgraph import Wave2LangGraphAdapter
        return Wave2LangGraphAdapter(tasks_dir=tasks_dir)
    if framework == "crewai":
        from sabot.adapters.wave2_crewai import Wave2CrewAIAdapter
        return Wave2CrewAIAdapter(tasks_dir=tasks_dir)
    if framework == "autogen":
        from sabot.adapters.wave2_autogen import Wave2AutoGenAdapter
        return Wave2AutoGenAdapter(tasks_dir=tasks_dir)
    raise SystemExit(f"unknown framework: {framework}")


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
    if usd >= WAVE2_CAP_USD:
        raise SystemExit(f"WAVE-2 BREAKER: projected spend ${usd:.2f} >= "
                         f"${WAVE2_CAP_USD:.0f} margined — stopping before the next "
                         "paid run. Surface to Jeff; never raise the breaker.")


def _ledger(out: Path, framework: str, entry: dict) -> None:
    line = json.dumps({"excluded": None, "detected_hard": False, "recovered": False,
                       "retried": 0, "skipped": None, **entry}, sort_keys=True)
    with (out / f"ledger-{framework}.jsonl").open("a") as f:
        f.write(line + "\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--framework", required=True,
                   choices=("langgraph", "crewai", "autogen"))
    p.add_argument("--seeds-file", required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--out-dir", default="runs/wave2")
    a = p.parse_args(argv)
    _load_key()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds = json.loads(Path(a.seeds_file).read_text())["seeds"]
    adapter = _adapter(a.framework, Path(a.tasks_dir))

    for config in CONFIGS:
        profile = run_profile(a.framework, config)
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
                            {"profile": profile, "runs": 1 + retried,
                             "cell": bkey.relpath(), "retried": retried})
                baseline_dead = baseline.error is not None or not baseline.task_passed
                for op in OPERATORS:
                    if is_carved_out(a.framework, config, op):
                        continue          # SPEC 10.6: not part of the matrix
                    key = CellKey(a.framework, config, task, op, seed)
                    cdir = out / key.relpath()
                    cdir.mkdir(parents=True, exist_ok=True)
                    vfile = cdir / "cellverdict.json"
                    if vfile.exists():
                        continue          # resume
                    if baseline_dead:
                        verdict = score(trace=baseline.trace, injection_seq=0,
                                        baseline_passed=baseline.task_passed,
                                        task_passed=False, injection_verified=False,
                                        run_error=baseline.error is not None)
                        vfile.write_text(cell_verdict_to_json(verdict))
                        _ledger(out, a.framework,
                                {"profile": profile, "runs": 0, "cell": key.relpath(),
                                 "excluded": verdict.excluded,
                                 "skipped": "baseline_excluded"})
                        continue
                    _check_cap(out)
                    cell = Cell(a.framework, task, config, op, SPECS[(task, op)], seed)
                    faulted, retried = _run_retry_once(adapter, cell)
                    (cdir / "runresult.json").write_text(run_result_to_json(faulted))
                    verdict = run_cell(adapter, cell, faulted, baseline)
                    vfile.write_text(cell_verdict_to_json(verdict))
                    _ledger(out, a.framework,
                            {"profile": profile, "runs": 1 + retried,
                             "cell": key.relpath(), "excluded": verdict.excluded,
                             "detected_hard": verdict.detected_hard,
                             "recovered": verdict.recovered, "retried": retried})
                    print(f"{key.relpath()}: excluded={verdict.excluded} "
                          f"hard={verdict.detected_hard} recovered={verdict.recovered}",
                          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
