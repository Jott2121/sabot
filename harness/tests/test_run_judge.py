import importlib.util, json, pathlib

import pytest

from sabot.judge.rubric import JudgeParseError
from sabot.judge.runner import JudgeVerdict
from sabot.runner import RunResult
from sabot.serde import cell_verdict_to_json, run_result_to_json
from sabot.score import CellVerdict
from sabot.trace import Event, Trace

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = pathlib.Path.home() / "sabot" / "tasks"


def _load():
    spec = importlib.util.spec_from_file_location("run_judge", ROOT / "scripts" / "run_judge.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cell(runs, relpath, excluded=None, detected_hard=False):
    d = runs / relpath
    d.mkdir(parents=True)
    fw, config, task, op, seed = relpath.split("/")
    t = Trace(run_id="r", framework=fw, task=task, config=config, operator=op,
              seed=int(seed.removeprefix("seed")))
    t.add(Event(kind="agent-msg", agent="worker", payload={"text": "hello"}, seq=1))
    r = RunResult(trace=t, task_passed=True, injection_seq=1, injection_verified=True)
    (d / "runresult.json").write_text(run_result_to_json(r))
    v = CellVerdict(detected_hard=detected_hard, reacted=detected_hard, recovered=True,
                    excluded=excluded, acts=())
    (d / "cellverdict.json").write_text(cell_verdict_to_json(v))


def _seed_runs(tmp_path, n=10):
    runs = tmp_path / "runs"
    for i in range(n):
        _cell(runs, f"langgraph/default/T1/O{(i % 6) + 1}/seed{i}")
    _cell(runs, "langgraph/default/T2/O1/seed99", excluded="RUN_ERROR")
    _cell(runs, "langgraph/default/T3/O1/seed99", detected_hard=True)
    return runs


def test_judged_set_batches_doubles_and_kappa(tmp_path, monkeypatch):
    mod = _load()
    runs = _seed_runs(tmp_path)
    sandbox_calls, judged = [], []
    monkeypatch.setattr(mod, "assert_sandboxed", lambda: sandbox_calls.append(1))
    def fake_judge(trace, note, prompt_variant=0):
        judged.append((trace.task, prompt_variant))
        assert note                                   # a real ground-truth note came through
        return JudgeVerdict(noticed=True, by_which_component="reviewer",
                            evidence_quote="looks off", raw="{}")
    monkeypatch.setattr(mod, "judge_cell", fake_judge)
    rc = mod.main(["--runs-dir", str(runs), "--tasks-dir", str(TASKS),
                   "--batch-size", "4"])
    assert rc == 0
    # 10 eligible cells (excluded + hard-detected are not judged): 3 batches of <=4
    assert len(sandbox_calls) == 3
    singles = [j for j in judged if j[1] == 0]
    doubles = [j for j in judged if j[1] == 1]
    assert len(singles) == 10 and len(doubles) == 2   # every 5th sorted relpath
    kap = json.loads((runs / "judge-kappa.json").read_text())
    assert kap["pairs"] == 2 and kap["kappa"] == 1.0 and kap["low_confidence"] is False


def test_parse_error_is_counted_exclusion_and_resume_skips(tmp_path, monkeypatch):
    mod = _load()
    runs = _seed_runs(tmp_path)
    monkeypatch.setattr(mod, "assert_sandboxed", lambda: None)
    calls = []
    def flaky(trace, note, prompt_variant=0):
        calls.append(1)
        if trace.operator == "O2":
            raise JudgeParseError("no JSON object found")
        return JudgeVerdict(noticed=False, by_which_component="", evidence_quote="", raw="{}")
    monkeypatch.setattr(mod, "judge_cell", flaky)
    assert mod.main(["--runs-dir", str(runs), "--tasks-dir", str(TASKS)]) == 0
    excluded = list(runs.rglob("judge-excluded.json"))
    assert len(excluded) >= 1
    kap = json.loads((runs / "judge-kappa.json").read_text())
    assert kap["judge_exclusions"] == len(excluded)
    n_first = len(calls)
    assert mod.main(["--runs-dir", str(runs), "--tasks-dir", str(TASKS)]) == 0
    assert len(calls) == n_first                      # full resume: zero re-judging
