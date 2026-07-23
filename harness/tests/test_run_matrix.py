# tests/test_run_matrix.py
import importlib.util, json, pathlib, sys

import pytest

from sabot.runner import RunResult
from sabot.trace import Event, Trace

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = pathlib.Path.home() / "sabot" / "tasks"


def _load_driver():
    spec = importlib.util.spec_from_file_location("run_matrix", ROOT / "scripts" / "run_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class StubAdapter:
    """Counts run() calls; scripted per-cell outcomes."""
    def __init__(self, baseline_passes=True, baseline_errors=0, faulted_errors=0):
        self.calls = []
        self._baseline_errors = baseline_errors
        self._faulted_errors = faulted_errors
        self.baseline_passes = baseline_passes

    def run(self, cell):
        self.calls.append((cell.task, cell.config, cell.operator, cell.seed))
        t = Trace(run_id="r", framework=cell.framework, task=cell.task,
                  config=cell.config, operator=cell.operator, seed=cell.seed)
        t.add(Event(kind="agent-msg", agent="worker", payload={"text": "out"}, seq=1))
        if cell.operator is None:
            if self._baseline_errors > 0:
                self._baseline_errors -= 1
                return RunResult(trace=t, task_passed=False, injection_seq=None,
                                 injection_verified=False, error="boom")
            return RunResult(trace=t, task_passed=self.baseline_passes,
                             injection_seq=None, injection_verified=False, error=None)
        if self._faulted_errors > 0:
            self._faulted_errors -= 1
            return RunResult(trace=t, task_passed=False, injection_seq=None,
                             injection_verified=False, error="boom")
        return RunResult(trace=t, task_passed=True, injection_seq=1,
                         injection_verified=True, error=None)


def _run(mod, tmp_path, adapter, seeds=(11,), framework="langgraph"):
    seeds_file = tmp_path / "seeds.json"
    seeds_file.write_text(json.dumps({"seeds": list(seeds)}))
    out = tmp_path / "runs"
    mod._adapter = lambda fw, td: adapter          # offline seam
    rc = mod.main(["--framework", framework, "--seeds-file", str(seeds_file),
                   "--tasks-dir", str(TASKS), "--out-dir", str(out)])
    return rc, out


def test_baseline_runs_once_per_group_and_all_cells_score(tmp_path):
    mod = _load_driver()
    a = StubAdapter()
    rc, out = _run(mod, tmp_path, a)
    assert rc == 0
    baseline_calls = [c for c in a.calls if c[2] is None]
    faulted_calls = [c for c in a.calls if c[2] is not None]
    # 2 configs x 5 tasks x 1 seed baselines; six operators each NEVER re-pay a baseline
    assert len(baseline_calls) == 10
    assert len(faulted_calls) == 60
    verdicts = list(out.rglob("cellverdict.json"))
    assert len(verdicts) == 60
    v = json.loads((out / "langgraph/default/T1/O1/seed11/cellverdict.json").read_text())
    assert v["excluded"] is None


def test_resume_skips_existing_and_reloads_baseline(tmp_path):
    mod = _load_driver()
    a = StubAdapter()
    _run(mod, tmp_path, a)
    first_calls = len(a.calls)
    b = StubAdapter()
    rc, out = _run(mod, tmp_path, b)
    assert rc == 0 and b.calls == []               # everything resumed, zero new runs
    assert first_calls == 70


def test_run_error_retried_once_then_baseline_group_short_circuits(tmp_path):
    mod = _load_driver()
    # every baseline attempt errors: 10 groups x 2 attempts; faulted arms NEVER run
    a = StubAdapter(baseline_errors=10**6)
    rc, out = _run(mod, tmp_path, a)
    assert rc == 0
    assert all(c[2] is None for c in a.calls)
    assert len(a.calls) == 20                       # retry-once per baseline group
    v = json.loads((out / "langgraph/default/T1/O1/seed11/cellverdict.json").read_text())
    assert v["excluded"] == "RUN_ERROR"


def test_baseline_task_fail_writes_baseline_fail_without_faulted_spend(tmp_path):
    mod = _load_driver()
    a = StubAdapter(baseline_passes=False)
    rc, out = _run(mod, tmp_path, a)
    assert rc == 0 and all(c[2] is None for c in a.calls)
    v = json.loads((out / "langgraph/guardrail/T5/O6/seed11/cellverdict.json").read_text())
    assert v["excluded"] == "BASELINE_FAIL"


def test_ledger_lines_and_cap_abort(tmp_path):
    mod = _load_driver()
    a = StubAdapter()
    _run(mod, tmp_path, a)
    ledger = (tmp_path / "runs" / "ledger-langgraph.jsonl").read_text().splitlines()
    assert all({"profile", "runs", "cell"} <= set(json.loads(l)) for l in ledger)
    # forge a ledger that busts the cap; next invocation must refuse to spend
    big = tmp_path / "runs" / "ledger-crewai.jsonl"
    big.write_text(json.dumps({"profile": "magentic", "runs": 10**6, "cell": "x",
                               "excluded": None, "detected_hard": False, "recovered": False,
                               "retried": 0, "output_chars": 0, "skipped": None}) + "\n")
    for f in (tmp_path / "runs").rglob("cellverdict.json"):
        f.unlink()                                  # force re-run attempts
    b = StubAdapter()
    with pytest.raises(SystemExit, match="HARD CAP"):
        _run(mod, tmp_path, b)


def test_baseline_retry_then_success_is_kept_and_ledger_shows_retry(tmp_path):
    mod = _load_driver()
    # first baseline attempt errors once; the retry succeeds and must be the kept result
    a = StubAdapter(baseline_errors=1)
    rc, out = _run(mod, tmp_path, a)
    assert rc == 0
    v = json.loads((out / "langgraph/default/T1/O1/seed11/cellverdict.json").read_text())
    assert v["excluded"] is None                # kept the successful retried baseline
    ledger = [json.loads(l) for l in
              (tmp_path / "runs" / "ledger-langgraph.jsonl").read_text().splitlines()]
    baseline_line = next(d for d in ledger
                         if d["cell"] == "langgraph/default/T1/baseline/seed11")
    assert baseline_line["runs"] == 2 and baseline_line["retried"] == 1


def test_faulted_run_error_after_two_failed_attempts_excludes_only_that_cell(tmp_path):
    mod = _load_driver()
    # the first faulted arm errors on BOTH attempts; sibling operators still score normally
    a = StubAdapter(faulted_errors=2)
    rc, out = _run(mod, tmp_path, a)
    assert rc == 0
    cell_dir = out / "langgraph/default/T1/O1/seed11"
    result = json.loads((cell_dir / "runresult.json").read_text())
    assert result["error"] == "boom"
    v = json.loads((cell_dir / "cellverdict.json").read_text())
    assert v["excluded"] == "RUN_ERROR"
    sibling = json.loads((out / "langgraph/default/T1/O2/seed11/cellverdict.json").read_text())
    assert sibling["excluded"] is None
