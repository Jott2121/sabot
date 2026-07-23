#!/usr/bin/env python
"""Run one Sabot cell (faulted + its baseline) and write serde JSON artifacts.
Must be executed with the target framework's venv python."""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.runner import Cell, run_cell
from sabot.serde import run_result_to_json, cell_verdict_to_json

def _load_key() -> None:
    key_file = Path.home() / ".config" / "oracle-gate" / "openai.key"
    os.environ.setdefault("OPENAI_API_KEY", key_file.read_text().strip())

def _adapter(framework: str, tasks_dir: Path):
    if framework == "langgraph":
        from sabot.adapters.langgraph_adapter import LangGraphAdapter
        from sabot.adapters.operator_specs import SPECS
        return LangGraphAdapter(tasks_dir=tasks_dir), SPECS
    if framework == "crewai":
        from sabot.adapters.crewai_adapter import CrewAIAdapter
        from sabot.adapters.operator_specs import SPECS
        return CrewAIAdapter(tasks_dir=tasks_dir), SPECS
    if framework == "autogen":
        from sabot.adapters.autogen_adapter import AutoGenAdapter
        from sabot.adapters.operator_specs import SPECS
        return AutoGenAdapter(tasks_dir=tasks_dir), SPECS
    raise SystemExit(f"unknown framework: {framework}")

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--framework", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--config", default="default")
    p.add_argument("--operator", default=None)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--tasks-dir", default=str(Path.home() / "sabot" / "tasks"))
    p.add_argument("--out-dir", required=True)
    a = p.parse_args()
    _load_key()
    tasks_dir = Path(a.tasks_dir)
    adapter, specs = _adapter(a.framework, tasks_dir)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    spec = specs.get((a.task, a.operator)) if a.operator else None
    baseline = adapter.run(Cell(framework=a.framework, task=a.task, config=a.config,
                                operator=None, operator_spec=None, seed=a.seed))
    (out / "baseline-runresult.json").write_text(run_result_to_json(baseline))
    if a.operator:
        faulted = adapter.run(Cell(framework=a.framework, task=a.task, config=a.config,
                                   operator=a.operator, operator_spec=spec, seed=a.seed))
        (out / "runresult.json").write_text(run_result_to_json(faulted))
        verdict = run_cell(adapter, Cell(framework=a.framework, task=a.task,
                                         config=a.config, operator=a.operator,
                                         operator_spec=spec, seed=a.seed),
                           faulted, baseline)
        (out / "cellverdict.json").write_text(cell_verdict_to_json(verdict))
        print(f"verdict: {verdict}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
