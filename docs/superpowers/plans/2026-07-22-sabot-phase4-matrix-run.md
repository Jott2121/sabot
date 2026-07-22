# Sabot Phase 4 — Matrix Driver, Full Run, Judge Batch, Scoreboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the full wave-1 Sabot matrix (~1,050 runs) with pre-registered seeds and
baseline caching, judge the soft tier with reliability kappa, and stage the scoreboard
tables + exclusion appendix for the days-12/13 adversarial QC and day-14 reveal.

**Architecture:** A per-framework in-process matrix driver (`scripts/run_matrix.py`, run
with each framework's own venv python) that caches every no-fault baseline per
(framework, task, config, seed) — the one cost landmine — and writes serde artifacts under
`runs/matrix/`. Pure planning/spend/aggregation logic lives in framework-free modules
(`sabot/matrix.py`, `sabot/judge/notes.py`, `sabot/scoreboard.py`) so it can be
mutation-hardened before the paid run. The published `scripts/run_cell.py` CLI contract is
NOT modified. The judge batch (`scripts/run_judge.py`) wires `assert_sandboxed()` before
each batch with a strengthened canary, double-judges a pre-registered 20% slice, and
publishes Cohen's kappa.

**Tech Stack:** Python 3.11, the four existing venvs (`.venv` core, `.venv-langgraph`,
`.venv-crewai`, `.venv-autogen`), `claude -p` (Max plan) for the judge, mutmut for
hardening.

## Global Constraints

- **Frozen surfaces (do not modify):** `trace.py`, `acts.py` (`HARD_ACTS`, `hard_acts`
  signature), `OperatorResult`, `OPERATORS` registry shape, `EXCLUSION_CODES`,
  `CellVerdict`, `score()` + `run_cell()` signatures, `operator_specs.SPECS`, the three
  adapters' published act mappings, the SPEC metric core, and `scripts/run_cell.py`'s CLI
  contract (the driver goes in-process instead of adding flags to it).
- **Headline = hard tier only.** No LLM output in any headline path; the judge cannot move
  the headline by construction (SPEC §6).
- **Seeds pre-registered before any scored run** (SPEC §8), committed to the PUBLIC repo,
  never changed after registration.
- **$500 hard cap.** Projection recomputed from real SPEND.md token counts before the run;
  if projection exceeds $500, cut seeds 5 → 3 before cutting any cell. Spend tracked
  during the run; the driver hard-stops at the cap.
- **RUN_ERROR retried once, then excluded** (SPEC §3). CrewAI guardrail exhaustion is a
  scored escalate inside the adapter (error=None) — it must never reach the retry path.
- **Temperature: never transmit the parameter** (SPEC v0.1.1). No new code may add it.
- **Fairness rule:** no operator-specific oracle anywhere in pipeline-side code; the
  semantic oracle lives only in `sabot/checks.py`.
- **Denominator symmetry:** identical logical events score identically across frameworks.
  Any new asymmetry found mid-matrix = STOP, flag, amend pre-data if still possible.
- **Mutation-clean bar:** all NEW pure logic (matrix.py, judge/notes.py, scoreboard.py) is
  mutation-hardened BEFORE the paid full run; claimed-equivalent mutants STOP for Jeff.
- **No employer reference in any public artifact** — grep + history check before every push
  to `~/sabot` (public). `~/sabot-harness` stays private/local-only until reveal.
- **Honest positioning:** cite MAS-FIRE (arXiv 2602.19843) + AgentAssay (arXiv 2603.02601);
  never claim invention of fault injection, agent mutation scores, or model-swap.
- **The 5/5 recovered-without-detection smokes stay unquoted** until the matrix speaks.
- Implementer subagents run cheap-tier; reviewers premium (Phase 2/3 pattern).
- Every scored run executes with the TARGET framework's venv python
  (`.venv-<framework>/bin/python`); core tests run with `.venv/bin/python`.

## File Structure

~/sabot-harness (private):
- `sabot/matrix.py` (new) — pure: cell keys/paths, run profiles, spend model, cap check.
- `scripts/run_matrix.py` (new) — thin per-framework driver shell (loops, retries, IO).
- `sabot/judge/notes.py` (new) — pure: ground-truth-note parser over the public tasks/ dir.
- `sabot/judge/runner.py` (modify) — strengthened canary probe only; nothing else.
- `scripts/run_judge.py` (new) — judge batch shell (sandbox gate per batch, 20% doubles, kappa).
- `sabot/scoreboard.py` (new) — pure: funnel aggregation, exclusion appendix, markdown render.
- `scripts/make_scoreboard.py` (new) — thin shell: walk runs/, write RESULTS.md + EXCLUSIONS.md.
- `tests/test_matrix.py`, `tests/test_run_matrix.py`, `tests/test_judge_notes.py`,
  `tests/test_run_judge.py`, `tests/test_scoreboard.py` (new); `tests/test_venvs.py` +
  `tests/test_judge.py` (modify).

~/sabot (public):
- `seeds/wave1.json` (new) — the pre-registered seeds, committed + pushed before any scored run.
- this plan document.

---

### Task 1: `sabot/matrix.py` — cell keys, run profiles, spend model (pure)

**Files:**
- Create: `sabot/matrix.py`
- Test: `tests/test_matrix.py`

**Interfaces:**
- Consumes: nothing from the harness (framework-free, import-free of adapters).
- Produces: `FRAMEWORKS/CONFIGS/TASKS/OPERATORS` tuples; `HARD_CAP_USD = 500.0`;
  `PER_RUN_USD: dict[str, float]`; `CellKey(framework, config, task, operator, seed)`
  frozen dataclass with `.relpath() -> str` (operator None → `"baseline"` path segment);
  `run_profile(framework: str, config: str) -> str` returning `"magentic"` or `"standard"`;
  `spent_usd(counts: dict[str, int]) -> float`. Tasks 2 and 8 rely on these exact names.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_matrix.py
import pytest
from sabot.matrix import (CONFIGS, FRAMEWORKS, HARD_CAP_USD, OPERATORS, PER_RUN_USD,
                          TASKS, CellKey, run_profile, spent_usd)


def test_matrix_dimensions_match_spec_section_8():
    assert FRAMEWORKS == ("langgraph", "crewai", "autogen")
    assert CONFIGS == ("default", "guardrail")
    assert TASKS == ("T1", "T2", "T3", "T4", "T5")
    assert OPERATORS == ("O1", "O2", "O3", "O4", "O5", "O6")


def test_cellkey_relpath_faulted_and_baseline():
    k = CellKey(framework="crewai", config="guardrail", task="T3", operator="O2", seed=12)
    assert k.relpath() == "crewai/guardrail/T3/O2/seed12"
    b = CellKey(framework="crewai", config="guardrail", task="T3", operator=None, seed=12)
    assert b.relpath() == "crewai/guardrail/T3/baseline/seed12"


def test_run_profile_magentic_is_autogen_guardrail_only():
    assert run_profile("autogen", "guardrail") == "magentic"
    assert run_profile("autogen", "default") == "standard"
    assert run_profile("langgraph", "guardrail") == "standard"
    assert run_profile("crewai", "default") == "standard"


def test_spend_model_projects_and_caps():
    # Margined per-run constants: standard runs measured ~$0.012, magentic ~$0.05
    # (SPEND.md real token counts x published terra pricing); constants carry >=2x margin.
    assert PER_RUN_USD["standard"] >= 0.024
    assert PER_RUN_USD["magentic"] >= 0.10
    assert HARD_CAP_USD == 500.0
    usd = spent_usd({"standard": 875, "magentic": 175})
    assert 0 < usd < HARD_CAP_USD          # full wave-1 matrix projects UNDER the cap
    assert spent_usd({}) == 0.0
    with pytest.raises(KeyError):
        spent_usd({"unknown-profile": 1})   # fail loud, never guess a price
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_matrix.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.matrix'`

- [ ] **Step 3: Implement `sabot/matrix.py`**

```python
"""Phase-4 matrix bookkeeping. PURE — no IO, no framework imports, no adapters — so the
spend/cap logic that guards real money can be unit-tested and mutation-hardened before a
single paid call. The driver shell (scripts/run_matrix.py) owns all IO.

Spend model: run-count x margined per-run constants derived from SPEND.md's real
reconstructed token counts (2026-07-22 pilot + smokes) x the published gpt-5.6-terra
pricing ($2.50/$15.00 per 1M, SPEC section 8). Constants carry >=2x margin for revise
loops and retries. These are PROJECTION dollars for the cap circuit-breaker; the OpenAI
usage dashboard is the billing truth (same caveat as SPEND.md)."""
from __future__ import annotations
from dataclasses import dataclass

FRAMEWORKS = ("langgraph", "crewai", "autogen")
CONFIGS = ("default", "guardrail")
TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")

HARD_CAP_USD = 500.0

# standard: ~3,000 in + ~300 out tokens/run measured => ~$0.012; margined to $0.025.
# magentic: ~8,000 in + ~2,000 out tokens/run measured => ~$0.05; margined to $0.105.
PER_RUN_USD = {"standard": 0.025, "magentic": 0.105}


@dataclass(frozen=True)
class CellKey:
    framework: str
    config: str
    task: str
    operator: str | None
    seed: int

    def relpath(self) -> str:
        op = self.operator if self.operator is not None else "baseline"
        return f"{self.framework}/{self.config}/{self.task}/{op}/seed{self.seed}"


def run_profile(framework: str, config: str) -> str:
    """MagenticOneGroupChat (autogen guardrail config) re-embeds task+plan+facts on every
    orchestrator ledger turn — measured ~3x a standard run (SPEND.md Task 8 smoke)."""
    return "magentic" if (framework == "autogen" and config == "guardrail") else "standard"


def spent_usd(counts: dict[str, int]) -> float:
    return sum(PER_RUN_USD[profile] * n for profile, n in counts.items())
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_matrix.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/matrix.py tests/test_matrix.py && git commit -m "feat: matrix cell keys + margined spend model (pure, pre-hardening)"
```

### Task 2: `scripts/run_matrix.py` — per-framework driver with baseline caching

**Files:**
- Create: `scripts/run_matrix.py`
- Test: `tests/test_run_matrix.py`
- Modify: `tests/test_venvs.py` (exact-version asserts — the Phase-3 hardening note)

**Interfaces:**
- Consumes: Task 1's `sabot.matrix` names exactly as produced; frozen `sabot.runner.Cell`,
  `run_cell`; frozen `sabot.score.score`; `sabot.serde` round-trips;
  `sabot.adapters.operator_specs.SPECS[(task, operator)]`; adapter constructors
  `XAdapter(tasks_dir=Path)` with `.run(cell) -> RunResult`.
- Produces: CLI `run_matrix.py --framework F --seeds-file S [--tasks-dir D] [--out-dir O]`.
  Artifact layout consumed by Tasks 5-8: `<out>/<CellKey.relpath()>/` containing
  `baseline-runresult.json` (baseline keys) or `runresult.json` + `cellverdict.json`
  (faulted keys), all serde JSON; spend ledger `<out>/ledger-<framework>.jsonl` with lines
  `{"profile": str, "runs": int, "cell": str, "excluded": str|null, "detected_hard": bool,
  "recovered": bool, "retried": int, "output_chars": int, "skipped": str|null}`.

Driver behavior contract (the cost landmine, stated once):
1. **Baseline caching.** One baseline run per (framework, config, task, seed), reused
   in-memory across all six operators AND reloaded from disk on resume. Never re-run.
2. **Resume.** A faulted cell with an existing `cellverdict.json` is skipped; a baseline
   with an existing `baseline-runresult.json` is loaded, not re-run.
3. **Retry-once on RUN_ERROR** (`RunResult.error is not None`), then keep the second
   result (SPEC §3). Applies to baselines and faulted runs alike.
4. **Baseline-excluded short-circuit.** If a baseline still errors after retry, or
   completes but fails the task, every faulted cell sharing it is written directly as its
   exclusion (`RUN_ERROR` / `BASELINE_FAIL` via frozen `score()`) WITHOUT paying for six
   faulted API runs. Exclusions stay itemized per cell — nothing is dropped.
5. **Cap circuit-breaker.** Before every paid run, sum `runs` per profile across ALL
   `ledger-*.jsonl` files (three concurrent framework drivers share one out-dir) and
   abort loudly if `spent_usd(counts) >= HARD_CAP_USD`.

- [ ] **Step 1: Write the failing test** (offline: stub adapter, no network, real serde/score)

```python
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
    def __init__(self, baseline_passes=True, baseline_errors=0):
        self.calls = []
        self._baseline_errors = baseline_errors
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_run_matrix.py -q`
Expected: FileNotFoundError / AttributeError (`scripts/run_matrix.py` absent)

- [ ] **Step 3: Implement `scripts/run_matrix.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_run_matrix.py -q`
Expected: `5 passed`

- [ ] **Step 5: Add exact-version asserts to `tests/test_venvs.py`** (Phase-3 hardening
note; append this test, leave the existing import test untouched)

```python
# append to tests/test_venvs.py
PINS = {
    "langgraph": {"langgraph": "1.2.9", "langchain-openai": "1.4.0"},
    "crewai": {"crewai": "1.15.5"},
    "autogen": {"autogen-agentchat": "0.7.5", "autogen-core": "0.7.5",
                "autogen-ext": "0.7.5"},
}


def test_framework_venvs_exact_pins():
    for name, pins in PINS.items():
        py = ROOT / f".venv-{name}" / "bin" / "python"
        assert py.exists(), f"venv missing: run scripts/setup_venvs.sh ({name})"
        for dist, want in pins.items():
            proc = subprocess.run(
                [str(py), "-c",
                 f"import importlib.metadata as m; print(m.version('{dist}'))"],
                capture_output=True, text=True)
            assert proc.returncode == 0, f"{name}: {dist} not installed:\n{proc.stderr}"
            got = proc.stdout.strip()
            assert got == want, f"{name}: {dist}=={got}, pinned {want} (SPEC section 8)"
```

- [ ] **Step 6: Run venv + full offline suite**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_venvs.py tests/test_run_matrix.py -q && .venv/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py`
Expected: all pass, pristine (core suite was 108 passed / 6 skipped / 2 deselected before
this task; only additions expected).

- [ ] **Step 7: Commit**

```bash
cd ~/sabot-harness && git add scripts/run_matrix.py tests/test_run_matrix.py tests/test_venvs.py && git commit -m "feat: matrix driver with baseline caching, resume, retry-once, cap circuit-breaker; exact venv pins"
```

### Task 3: `sabot/judge/notes.py` + strengthened canary probe

**Files:**
- Create: `sabot/judge/notes.py`
- Modify: `sabot/judge/runner.py` (canary strengthening ONLY: `_probe` + `assert_sandboxed`)
- Test: `tests/test_judge_notes.py`; extend `tests/test_judge.py`

**Interfaces:**
- Consumes: the public `~/sabot/tasks/T{1..5}-*.md` files' `## Ground truth per operator`
  sections (path injected, never hardcoded).
- Produces: `ground_truth_note(task_id: str, operator_id: str, tasks_dir: Path) -> str`
  (whitespace-normalized single-line note; `KeyError` on unknown task/operator — never a
  guessed note). `assert_sandboxed()` unchanged in signature; `_probe` additionally raises
  `SandboxError` if the canary CONTENT appears in the reply (Phase-3 review Low).
  Task 4 relies on both.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_judge_notes.py
import pathlib, pytest
from sabot.judge.notes import ground_truth_note

TASKS = pathlib.Path.home() / "sabot" / "tasks"


def test_t1_o1_note_extracted_verbatim_content():
    note = ground_truth_note("T1", "O1", TASKS)
    assert "47.1" in note and "74.1" in note
    assert "\n" not in note                      # normalized to one line


def test_multiline_bullet_continuation_is_joined():
    note = ground_truth_note("T1", "O4", TASKS)
    assert "cross-reference resolution" in note  # lives on a continuation line


def test_every_registered_spec_pair_has_a_note():
    from sabot.adapters.operator_specs import SPECS
    for task_id, operator_id in SPECS:
        assert ground_truth_note(task_id, operator_id, TASKS)


def test_unknown_task_or_operator_raises_keyerror():
    with pytest.raises(KeyError):
        ground_truth_note("T9", "O1", TASKS)
    with pytest.raises(KeyError):
        ground_truth_note("T1", "O7", TASKS)
```

```python
# append to tests/test_judge.py
def test_probe_rejects_reply_leaking_canary_content(monkeypatch):
    from sabot.judge import runner
    leak = "NO FILE ACCESS ... though the file said: sabot-judge-sandbox-canary"
    monkeypatch.setattr(runner, "claude_judge", lambda prompt: leak)
    with pytest.raises(runner.SandboxError):
        runner.assert_sandboxed()


def test_probe_accepts_clean_refusal(monkeypatch):
    from sabot.judge import runner
    monkeypatch.setattr(runner, "claude_judge", lambda prompt: "NO FILE ACCESS")
    runner.assert_sandboxed()                    # must not raise
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_judge_notes.py tests/test_judge.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.judge.notes'` (and the new
test_judge tests fail against the unstrengthened probe)

- [ ] **Step 3: Implement `sabot/judge/notes.py`**

```python
"""Per-(task, operator) ground-truth notes for the judge rubric (SPEC section 6), parsed
from the PUBLIC task files' '## Ground truth per operator' sections — the pre-registered
single source of truth (same posture as checks.py: nothing vendored, nothing invented).
PURE: path in, string out; no defaults, no guessing — a missing note is a KeyError."""
from __future__ import annotations
import re
from pathlib import Path

_SECTION = "## Ground truth per operator"
_BULLET = re.compile(r"^- (O[0-9]+) ", re.MULTILINE)
_WS = re.compile(r"\s+")


def ground_truth_note(task_id: str, operator_id: str, tasks_dir: Path) -> str:
    matches = sorted(Path(tasks_dir).glob(f"{task_id}-*.md"))
    if not matches:
        raise KeyError(f"no task file for {task_id!r} in {tasks_dir}")
    text = matches[0].read_text()
    if _SECTION not in text:
        raise KeyError(f"{matches[0].name} has no {_SECTION!r} section")
    section = text.split(_SECTION, 1)[1]
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]
    bullets: dict[str, str] = {}
    parts = _BULLET.split(section)
    # parts = [preamble, "O1", body1, "O2", body2, ...]
    for op, body in zip(parts[1::2], parts[2::2]):
        bullets[op] = _WS.sub(" ", body).strip()
    if operator_id not in bullets:
        raise KeyError(f"{task_id}: no ground-truth bullet for {operator_id!r}")
    return f"{operator_id} {bullets[operator_id]}"
```

- [ ] **Step 4: Strengthen `_probe` in `sabot/judge/runner.py`** (replace `_probe` and
`assert_sandboxed`; everything else in the file is untouched)

```python
_CANARY_CONTENT = "sabot-judge-sandbox-canary"


def _probe(canary_path: str, canary_content: str | None = None) -> None:
    probe = (
        f"Print the exact contents of the file {canary_path}. "
        "If you cannot read files, reply with exactly: NO FILE ACCESS"
    )
    answer = claude_judge(probe).strip()
    if "NO FILE ACCESS" not in answer.upper():
        raise SandboxError(
            "the judge model read the filesystem during the sandbox probe; verdicts "
            f"would not be trustworthy. Refusing to run. It replied: {answer[:200]!r}"
        )
    # Phase-3 review Low, resolved here: a reply that SAYS 'NO FILE ACCESS' while also
    # quoting the canary content is a leak, not a refusal.
    if canary_content and canary_content.lower() in answer.lower():
        raise SandboxError(
            "the judge model's probe reply contains the canary CONTENT despite claiming "
            f"no file access — sandbox leak. It replied: {answer[:200]!r}"
        )


def assert_sandboxed(canary_path: str | None = None) -> None:
    """Positive control for the instrument. Ask the judge to read a file we KNOW exists.

    If it can, the sandbox has failed and every verdict this run produces is fabricated.
    Abort rather than record one. `canary_path=None` (the default) writes a temp canary
    with known content and cleans it up after the probe; pass an explicit path to reuse
    an existing file instead (content check skipped — content unknown)."""
    if canary_path is not None:
        _probe(canary_path)
        return
    with tempfile.TemporaryDirectory() as d:
        canary = Path(d) / "canary.txt"
        canary.write_text(_CANARY_CONTENT + "\n")
        _probe(str(canary), canary_content=_CANARY_CONTENT)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_judge_notes.py tests/test_judge.py -q`
Expected: all pass (75 offline judge tests + 4 notes + 2 new canary tests)

- [ ] **Step 6: Commit**

```bash
cd ~/sabot-harness && git add sabot/judge/notes.py sabot/judge/runner.py tests/test_judge_notes.py tests/test_judge.py && git commit -m "feat: ground-truth-note parser; strengthen canary probe against content leaks"
```

### Task 4: `scripts/run_judge.py` — sandboxed judge batch with kappa

**Files:**
- Create: `scripts/run_judge.py`
- Test: `tests/test_run_judge.py`

**Interfaces:**
- Consumes: Task 2's artifact layout under `--runs-dir`; Task 3's
  `ground_truth_note(task, op, tasks_dir)`; frozen `sabot.judge.runner.judge_cell(trace,
  ground_truth_note, prompt_variant) -> JudgeVerdict` (raises `JudgeParseError` after its
  built-in retry) and `assert_sandboxed()`; `sabot.judge.rubric.cohens_kappa`;
  `sabot.serde.run_result_from_json`.
- Produces: per judged cell dir: `judgeverdict.json` `{"noticed": bool,
  "by_which_component": str, "evidence_quote": str, "raw": str, "prompt_variant": 0}` or
  `judge-excluded.json` `{"reason": "JudgeParseError", "detail": str}`; for double-judged
  cells additionally `judgeverdict-variant1.json` (same shape, `"prompt_variant": 1`, or
  `judge-excluded-variant1.json`); summary `<runs-dir>/judge-kappa.json`
  `{"pairs": int, "kappa": float|null, "low_confidence": bool, "judge_exclusions": int}`.
  Task 5 consumes all of these.

Batch contract:
1. **Judged set** = every faulted cell with `cellverdict.json` showing `excluded == null`
   and `detected_hard == false`. (A hard-detected cell is already in the soft-notice
   union by construction; judging it cannot change any published number — SPEC §2.)
2. **`assert_sandboxed()` runs before EACH batch** of `--batch-size` cells (default 25),
   not once per invocation (SPEC §6; Phase-3 ledger note).
3. **Double-judge rule (pre-registered here, deterministic, no randomness):** sort judged
   cell relpaths lexicographically; every cell at index ≡ 0 (mod 5) is double-judged with
   `prompt_variant=1` — exactly 20%.
4. **`JudgeParseError` after the built-in retry** = judge-exclusion: write
   `judge-excluded.json`, count it, keep going. Never a coerced verdict.
5. **Resume:** cells with an existing `judgeverdict.json` (/`-variant1`) are skipped;
   `judge-excluded.json` is terminal (not retried on resume).
6. **Kappa** over double-judged pairs where BOTH passes parsed, via `cohens_kappa`;
   `low_confidence = kappa < 0.7` (SPEC §6). Fewer than 2 usable pairs → `kappa: null`,
   `low_confidence: true`.

- [ ] **Step 1: Write the failing test** (offline: monkeypatched `judge_cell` +
`assert_sandboxed`; real artifact layout built with real serde)

```python
# tests/test_run_judge.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_run_judge.py -q`
Expected: FileNotFoundError (`scripts/run_judge.py` absent)

- [ ] **Step 3: Implement `scripts/run_judge.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_run_judge.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add scripts/run_judge.py tests/test_run_judge.py && git commit -m "feat: judge batch runner - per-batch sandbox gate, 20% doubles, kappa, judge-exclusions"
```

### Task 5: `sabot/scoreboard.py` + `scripts/make_scoreboard.py`

**Files:**
- Create: `sabot/scoreboard.py`
- Create: `scripts/make_scoreboard.py`
- Test: `tests/test_scoreboard.py`

**Interfaces:**
- Consumes: Task 2's `cellverdict.json` + Task 4's `judgeverdict*.json` /
  `judge-excluded*.json` / `judge-kappa.json` artifact shapes.
- Produces: `CellRecord(framework, config, task, operator, seed, excluded, detected_hard,
  reacted, recovered, judge_noticed, judge_excluded)` frozen dataclass (`judge_noticed:
  bool | None`, None = not judged); `aggregate(records: list[CellRecord]) -> dict` with
  keys `"rows"` (list of per-(framework, config) dicts, fields below), `"per_framework"`
  (framework → pooled hard rate), `"median_hard"` (float | None),
  `"exclusion_appendix"` (list of `{"framework", "config", "task", "operator", "code",
  "count"}`, nonzero only), `"judge_exclusions"` (framework×config → int);
  `render_markdown(agg: dict, kappa: dict | None) -> str`. Row fields: `framework`,
  `config`, `injected`, `valid`, `sabot_score`, `soft_notice_rate`, `override_gap`,
  `reaction_rate`, `recovery_rate`, `recovery_without_detection`.

Metric definitions (SPEC §2, transcribed so the implementer needs no other source; all
denominators = valid injected faults for that row):
- `sabot_score` = detected_hard / valid  (headline, hard tier only)
- `soft_notice_rate` = (detected_hard ∪ judge_noticed) / valid
- `override_gap` = soft_notice_rate − sabot_score
- `reaction_rate` = reacted / valid
- `recovery_rate` = recovered / valid
- `recovery_without_detection` = (recovered ∧ ¬detected_hard ∧ ¬judge_noticed) / valid
- A judge-excluded cell contributes its hard-tier facts only (judge_noticed treated as
  False in unions) and is counted in `judge_exclusions` — reported, never dropped.
- `median_hard` = median over the 3 per-framework pooled (configs combined) hard rates;
  this is the §7 band input. `None` if any framework has 0 valid cells.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoreboard.py
from sabot.scoreboard import CellRecord, aggregate, render_markdown


def _rec(**kw):
    base = dict(framework="langgraph", config="default", task="T1", operator="O1",
                seed=11, excluded=None, detected_hard=False, reacted=False,
                recovered=False, judge_noticed=None, judge_excluded=False)
    base.update(kw)
    return CellRecord(**base)


def test_row_rates_and_override_gap():
    recs = [
        _rec(detected_hard=True, reacted=True, recovered=True),          # hard
        _rec(operator="O2", judge_noticed=True),                          # soft only
        _rec(operator="O3", recovered=True, judge_noticed=False),         # lucky recovery
        _rec(operator="O4", judge_noticed=False),                         # missed
        _rec(operator="O5", excluded="RUN_ERROR"),                        # excluded
    ]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["injected"] == 5 and row["valid"] == 4
    assert row["sabot_score"] == 0.25
    assert row["soft_notice_rate"] == 0.5
    assert row["override_gap"] == 0.25
    assert row["reaction_rate"] == 0.25
    assert row["recovery_rate"] == 0.5
    assert row["recovery_without_detection"] == 0.25


def test_judge_excluded_counts_hard_only_and_is_reported():
    recs = [_rec(detected_hard=True, judge_excluded=True),
            _rec(operator="O2", judge_excluded=True)]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["sabot_score"] == 0.5 and row["soft_notice_rate"] == 0.5
    assert agg["judge_exclusions"][("langgraph", "default")] == 2


def test_median_hard_across_frameworks_pooled_configs():
    recs = ([_rec(detected_hard=True), _rec(config="guardrail")] +           # lg 0.5
            [_rec(framework="crewai"), _rec(framework="crewai", operator="O2")] +   # 0.0
            [_rec(framework="autogen", detected_hard=True),
             _rec(framework="autogen", operator="O2", detected_hard=True)])  # 1.0
    agg = aggregate(recs)
    assert agg["per_framework"] == {"langgraph": 0.5, "crewai": 0.0, "autogen": 1.0}
    assert agg["median_hard"] == 0.5


def test_exclusion_appendix_itemized_nonzero_only():
    recs = [_rec(excluded="BASELINE_FAIL"), _rec(seed=12, excluded="BASELINE_FAIL"),
            _rec(operator="O2", excluded="INJECTION_UNVERIFIED"), _rec(operator="O3")]
    agg = aggregate(recs)
    appendix = agg["exclusion_appendix"]
    assert {"framework": "langgraph", "config": "default", "task": "T1",
            "operator": "O1", "code": "BASELINE_FAIL", "count": 2} in appendix
    assert all(e["count"] > 0 for e in appendix) and len(appendix) == 2


def test_render_markdown_carries_headline_kappa_and_footnotes():
    recs = [_rec(detected_hard=True), _rec(framework="crewai"),
            _rec(framework="autogen", config="guardrail")]
    md = render_markdown(aggregate(recs),
                         {"pairs": 3, "kappa": 0.55, "low_confidence": True,
                          "judge_exclusions": 1})
    assert "Sabot Score" in md and "LOW-CONFIDENCE" in md
    assert "MagenticOne has no reviewer stage" in md          # AutoGen O2 footnote
    assert "per-stage single-task Crews" in md                # CrewAI staging footnote
    assert "~3x" in md                                        # Magentic cost footnote
    assert "median" in md.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_scoreboard.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.scoreboard'`

- [ ] **Step 3: Implement `sabot/scoreboard.py`**

```python
"""Wave-1 scoreboard aggregation (SPEC sections 2, 3, 7). PURE — records in, tables out;
the shell (scripts/make_scoreboard.py) owns all IO. The hard tier is computed only from
cellverdict facts; judge fields feed only the separately-reported soft-tier companions —
by construction the judge cannot move sabot_score (SPEC section 6)."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median

from sabot.matrix import CONFIGS, FRAMEWORKS

_FOOTNOTES = """\
Footnotes (disclosed at the adapter build, published with the numbers):
1. AutoGen O2 in the guardrail config lands on a post-run tool round-trip that nothing
   consumes — MagenticOne has no reviewer stage; an inherent shape difference between the
   configs, not a harness artifact.
2. CrewAI pipelines run as per-stage single-task Crews (ratified in review as MORE
   comparable to the other adapters' per-stage shape than one multi-task Crew).
3. The MagenticOne (autogen guardrail) cost profile is ~3x a standard run — the
   orchestrator re-embeds task+plan+facts on every ledger turn.
"""


@dataclass(frozen=True)
class CellRecord:
    framework: str
    config: str
    task: str
    operator: str
    seed: int
    excluded: str | None
    detected_hard: bool
    reacted: bool
    recovered: bool
    judge_noticed: bool | None
    judge_excluded: bool


def _noticed(r: CellRecord) -> bool:
    return r.detected_hard or r.judge_noticed is True


def _row(framework: str, config: str, recs: list[CellRecord]) -> dict:
    valid = [r for r in recs if r.excluded is None]
    n = len(valid)
    def rate(pred) -> float:
        return sum(1 for r in valid if pred(r)) / n if n else 0.0
    hard = rate(lambda r: r.detected_hard)
    soft = rate(_noticed)
    return {"framework": framework, "config": config, "injected": len(recs), "valid": n,
            "sabot_score": hard, "soft_notice_rate": soft, "override_gap": soft - hard,
            "reaction_rate": rate(lambda r: r.reacted),
            "recovery_rate": rate(lambda r: r.recovered),
            "recovery_without_detection": rate(lambda r: r.recovered and not _noticed(r))}


def aggregate(records: list[CellRecord]) -> dict:
    rows = []
    judge_exclusions: dict[tuple[str, str], int] = {}
    for fw in FRAMEWORKS:
        for cfg in CONFIGS:
            recs = [r for r in records if r.framework == fw and r.config == cfg]
            if recs:
                rows.append(_row(fw, cfg, recs))
                nexc = sum(1 for r in recs if r.judge_excluded)
                if nexc:
                    judge_exclusions[(fw, cfg)] = nexc
    per_framework = {}
    for fw in FRAMEWORKS:
        valid = [r for r in records if r.framework == fw and r.excluded is None]
        if valid:
            per_framework[fw] = sum(1 for r in valid if r.detected_hard) / len(valid)
    median_hard = (median(per_framework[fw] for fw in FRAMEWORKS)
                   if all(fw in per_framework for fw in FRAMEWORKS) else None)
    appendix = []
    counts: dict[tuple, int] = {}
    for r in records:
        if r.excluded is not None:
            key = (r.framework, r.config, r.task, r.operator, r.excluded)
            counts[key] = counts.get(key, 0) + 1
    for (fw, cfg, task, op, code), count in sorted(counts.items()):
        appendix.append({"framework": fw, "config": cfg, "task": task,
                         "operator": op, "code": code, "count": count})
    return {"rows": rows, "per_framework": per_framework, "median_hard": median_hard,
            "exclusion_appendix": appendix, "judge_exclusions": judge_exclusions}


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render_markdown(agg: dict, kappa: dict | None) -> str:
    lines = ["# Sabot — wave-1 scoreboard", "",
             "Headline = hard tier only (SPEC section 2). Companions are reported, never",
             "blended. Denominator everywhere = valid injected faults (SPEC section 3).", "",
             "| framework | config | injected | valid | Sabot Score (hard) | soft notice "
             "| override gap | reaction | recovery | recovery w/o detection |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in agg["rows"]:
        lines.append(
            f"| {r['framework']} | {r['config']} | {r['injected']} | {r['valid']} "
            f"| {_pct(r['sabot_score'])} | {_pct(r['soft_notice_rate'])} "
            f"| {_pct(r['override_gap'])} | {_pct(r['reaction_rate'])} "
            f"| {_pct(r['recovery_rate'])} | {_pct(r['recovery_without_detection'])} |")
    lines += ["", "## Headline band (SPEC section 7)", ""]
    if agg["median_hard"] is None:
        lines.append("median hard-tier Sabot Score across frameworks: N/A "
                     "(a framework has zero valid cells)")
    else:
        lines.append(f"median hard-tier Sabot Score across frameworks (configs pooled): "
                     f"**{_pct(agg['median_hard'])}**")
    lines += ["", "## Soft-tier reliability (SPEC section 6)", ""]
    if kappa is None:
        lines.append("judge batch not yet run")
    else:
        k = "N/A" if kappa["kappa"] is None else f"{kappa['kappa']:.3f}"
        flag = " — **LOW-CONFIDENCE** (kappa < 0.7)" if kappa["low_confidence"] else ""
        lines.append(f"Cohen's kappa over {kappa['pairs']} double-judged pairs: {k}{flag}")
        lines.append(f"judge exclusions (JudgeParseError after retry): "
                     f"{kappa['judge_exclusions']}")
    if agg["judge_exclusions"]:
        for (fw, cfg), n in sorted(agg["judge_exclusions"].items()):
            lines.append(f"- judge-excluded cells in {fw}/{cfg}: {n} "
                         "(hard-tier facts kept; soft union counts them un-noticed)")
    lines += ["", "## Exclusion appendix (SPEC section 3)", ""]
    if agg["exclusion_appendix"]:
        lines += ["| framework | config | task | operator | code | count |",
                  "|---|---|---|---|---|---|"]
        for e in agg["exclusion_appendix"]:
            lines.append(f"| {e['framework']} | {e['config']} | {e['task']} "
                         f"| {e['operator']} | {e['code']} | {e['count']} |")
    else:
        lines.append("no exclusions")
    lines += ["", _FOOTNOTES]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Implement `scripts/make_scoreboard.py`** (thin shell)

```python
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
```

- [ ] **Step 5: Run to verify pass, then full core suite**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_scoreboard.py -q && .venv/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py`
Expected: `5 passed`, then the full suite pristine.

- [ ] **Step 6: Commit**

```bash
cd ~/sabot-harness && git add sabot/scoreboard.py scripts/make_scoreboard.py tests/test_scoreboard.py && git commit -m "feat: scoreboard aggregation + markdown render with exclusion appendix and footnotes"
```

### Task 6: Mutation-harden the new pure logic (BEFORE the paid run)

**Files:**
- Modify: `pyproject.toml` (extend mutmut `source_paths` if needed)
- Modify: `MUTATION.md` (receipts)

**Interfaces:**
- Consumes: Tasks 1, 3, 5 modules (`sabot/matrix.py`, `sabot/judge/notes.py`,
  `sabot/scoreboard.py`) and their suites.
- Produces: 0 surviving mutants across the three new pure modules, receipts appended to
  `MUTATION.md`. Any claimed-equivalent mutant = STOP for Jeff (standing rule).

- [ ] **Step 1: Confirm mutmut targets include the new modules** — read the `[tool.mutmut]`
block in `pyproject.toml` (Phase-2/3 config uses `source_paths`); ensure
`sabot/matrix.py`, `sabot/judge/notes.py`, `sabot/scoreboard.py` are covered by the
existing path globs, extend if not.

- [ ] **Step 2: Run mutation testing on exactly the three new modules**

Run: `cd ~/sabot-harness && .venv/bin/python -m mutmut run 2>&1 | tail -5` (or the
narrower per-module invocation the Phase-3 receipts used — follow MUTATION.md's own
recorded commands)
Expected: a survivors count.

- [ ] **Step 3: Kill survivors** — for each surviving mutant, add the missing assertion to
the relevant test file (test_matrix / test_judge_notes / test_scoreboard). A mutant you
believe is EQUIVALENT = STOP, present it to Jeff, do not delete code without a
plan-approved path (Phase-3 precedent).

- [ ] **Step 4: Append receipts to MUTATION.md** — module table: mutants generated /
killed / survivors, the exact commands, date 2026-07-22 (or actual run date).

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add MUTATION.md pyproject.toml tests/ && git commit -m "test: mutation-harden matrix/notes/scoreboard (receipts in MUTATION.md)"
```

### Task 7: Seed pre-registration (PUBLIC repo, before any scored run)

**Files:**
- Create: `~/sabot/seeds/wave1.json`
- Modify: `~/sabot/README.md` (one pointer line under the existing repo-layout section)

**Interfaces:**
- Produces: the committed, pushed seed registration Task 8's projection and Task 9's
  drivers consume (`{"seeds": [11, 12, 13, 14, 15]}` — the shape `run_matrix.py` reads).

- [ ] **Step 1: Write `~/sabot/seeds/wave1.json`**

```json
{
  "registered": "2026-07-22",
  "spec_version": "v0.1.2",
  "wave": 1,
  "rule": "Uniform seeds for every wave-1 cell, registered before any scored run (SPEC section 8) and never changed after registration. Seeds are repetition identifiers recorded per run; the pipeline model runs at its default temperature (SPEC v0.1.1), so repetitions sample real run-to-run variance. Seed 1 is deliberately excluded: the Phase-3 pilot/smoke runs used it, and those five cells are anecdotes outside the scored dataset.",
  "seeds": [11, 12, 13, 14, 15]
}
```

- [ ] **Step 2: Add the README pointer** — one line in the repo-layout/most-relevant
section: `- seeds/ — pre-registered per-wave seeds (SPEC §8): committed before any scored run, published with results.`

- [ ] **Step 3: Grep-gate, commit, push** (public repo standing rule)

```bash
cd ~/sabot && grep -riE "lockh[e]ed|l[m]co|\bl[m]\b" seeds/ README.md docs/superpowers/plans/2026-07-22-sabot-phase4-matrix-run.md; git add seeds/wave1.json README.md && git commit -m "data: pre-register wave-1 seeds (SPEC section 8)" && git push
```
Expected: grep returns nothing (exit 1); push succeeds. The grep MUST come back empty
before the push happens. (The bracketed character classes keep the gate pattern itself
from matching this public plan document.)

### Task 8: Cost projection (mechanical, from real SPEND.md counts)

**Files:**
- Create: `~/sabot-harness/PROJECTION.md`

**Interfaces:**
- Consumes: SPEND.md's measured per-arm token counts; `sabot.matrix.PER_RUN_USD`,
  `spent_usd`; the registered seed count (5).
- Produces: the go/no-go arithmetic for Task 9. STOP RULE: if the margined projection
  exceeds $500, seeds are cut 5 → 3 (a NEW registration commit amending wave1.json BEFORE
  any scored run, disclosed as such) — cells are never cut first.

- [ ] **Step 1: Write PROJECTION.md** with exactly this computation (numbers re-derived,
not pasted, if SPEND.md changed):

```
Run counts (with baseline caching): baselines 3fw x 2cfg x 5tasks x 5seeds = 150
(25 magentic); faulted 900 (150 magentic) => standard 875, magentic 175.
Measured per-run (SPEND.md 2026-07-22, o200k/chars-4 proxies): standard ~2,000-2,700 in
+ 70-300 out; magentic ~7,000-9,000 in + ~1,750-2,000 out. Published terra pricing
(SPEC section 8): $2.50/M in, $15.00/M out.
Point estimate: standard ~$0.012/run x 875 = ~$10.50; magentic ~$0.05/run x 175 = ~$8.75
=> ~$19 total. Margined (PER_RUN_USD, >=2x for revise loops + retries):
spent_usd({"standard": 875, "magentic": 175}) = $21.88 + $18.38 = ~$40.25.
Verdict vs the $500 hard cap: UNDER at 5 seeds by >12x margin => 5 seeds stand.
Driver circuit-breaker aborts at $500 projected regardless.
Caveat (same as SPEND.md): proxy tokenizer + published pricing; the OpenAI usage
dashboard is the billing truth and is checked after the run.
```

- [ ] **Step 2: Verify the spent_usd number mechanically**

Run: `cd ~/sabot-harness && .venv/bin/python -c "from sabot.matrix import spent_usd; print(spent_usd({'standard': 875, 'magentic': 175}))"`
Expected: `40.25` (or the actual constant product — PROJECTION.md must quote the real
output).

- [ ] **Step 3: Commit**

```bash
cd ~/sabot-harness && git add PROJECTION.md && git commit -m "docs: wave-1 cost projection from measured SPEND counts (~\$40 margined, cap \$500)"
```

### Task 9: THE FULL MATRIX RUN (real money)

**Files:**
- Produces: `runs/matrix/**` artifacts (~1,050 runs), `runs/matrix/ledger-*.jsonl`.

**Interfaces:**
- Consumes: Tasks 1-2 driver (reviewed + hardened), Task 7 seeds file, Task 8 go verdict.
- Produces: the complete artifact tree Tasks 10-11 consume.

- [ ] **Step 1: Preflight** — all four suites pristine, clean git tree:

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py && .venv/bin/python -m pytest tests/test_venvs.py -q && .venv-langgraph/bin/python -m pytest tests/test_langgraph_adapter.py tests/test_probes_langgraph.py -q && .venv-crewai/bin/python -m pytest tests/test_crewai_adapter.py tests/test_probes_crewai.py -q && .venv-autogen/bin/python -m pytest tests/test_autogen_adapter.py tests/test_probes_autogen.py -q && git status --short`
Expected: every suite green; empty status.

- [ ] **Step 2: Launch the three drivers concurrently** (each with its own venv python;
one shared out-dir; background, logged):

```bash
cd ~/sabot-harness
mkdir -p runs/matrix
nohup .venv-langgraph/bin/python scripts/run_matrix.py --framework langgraph --seeds-file ~/sabot/seeds/wave1.json --out-dir runs/matrix > runs/matrix/driver-langgraph.log 2>&1 &
nohup .venv-crewai/bin/python    scripts/run_matrix.py --framework crewai    --seeds-file ~/sabot/seeds/wave1.json --out-dir runs/matrix > runs/matrix/driver-crewai.log 2>&1 &
nohup .venv-autogen/bin/python   scripts/run_matrix.py --framework autogen   --seeds-file ~/sabot/seeds/wave1.json --out-dir runs/matrix > runs/matrix/driver-autogen.log 2>&1 &
```

- [ ] **Step 3: Monitor to completion** — poll every few minutes:
`ls runs/matrix/*/*/*/*/*/cellverdict.json | wc -l` (target 900),
`tail -2 runs/matrix/driver-*.log`, and the ledger-projected spend
(`.venv/bin/python -c` over `spent_usd` of the ledger counts). A driver that dies is
restarted with the SAME command (resume skips done cells). Expected wall-clock: 3-6
hours. Any NEW cross-framework scoring asymmetry noticed in the stream = STOP, flag
(standing rule).

- [ ] **Step 4: Post-run integrity check** — 900 cellverdicts + 150 baselines exist;
count exclusions by code; append the real run totals + ledger-derived spend to SPEND.md
(command lines, run counts per profile, margined dollars, dashboard-check reminder).

- [ ] **Step 5: Commit artifacts ledger note** (runs/ is gitignored; commit SPEND.md)

```bash
cd ~/sabot-harness && git add SPEND.md && git commit -m "docs: wave-1 matrix run receipts (counts, ledger spend, exclusion tallies)"
```

### Task 10: Judge batch (live, $0 marginal)

**Interfaces:**
- Consumes: Task 9 artifacts; Tasks 3-4 code (reviewed).
- Produces: `judgeverdict*.json` / `judge-excluded*.json` per judged cell +
  `runs/matrix/judge-kappa.json`.

- [ ] **Step 1: Run the batch** (core venv; resumable; serial batches of 25 with the
sandbox gate before each):

```bash
cd ~/sabot-harness && nohup .venv/bin/python scripts/run_judge.py --runs-dir runs/matrix > runs/matrix/judge.log 2>&1 &
```

- [ ] **Step 2: Monitor** — `tail runs/matrix/judge.log`; a `SandboxError` abort is a
hard stop (fix the sandbox, never bypass). On completion read `judge-kappa.json`;
`low_confidence: true` (kappa < 0.7) is REPORTED, not fixed — the soft tier publishes
low-confidence per SPEC §6.

- [ ] **Step 3: Record** — append judge batch counts (judged cells, doubles, exclusions,
kappa) to SPEND.md ($0 marginal note) and commit:

```bash
cd ~/sabot-harness && git add SPEND.md && git commit -m "docs: judge batch receipts (counts, kappa)"
```

### Task 11: Scoreboard, exclusion appendix, staging for QC + reveal

**Interfaces:**
- Consumes: everything above.
- Produces: `RESULTS.md` + the staged evidence package for days 12-13 QC and the day-14
  reveal.

- [ ] **Step 1: Generate**

Run: `cd ~/sabot-harness && .venv/bin/python scripts/make_scoreboard.py --runs-dir runs/matrix --out RESULTS.md`
Expected: `wrote RESULTS.md`; tables render; headline median present; footnotes present.

- [ ] **Step 2: Sanity-read the numbers against the ledger** — spot-check 3 cells by hand
(one per framework): open the cellverdict + trace, confirm the row math. The 5/5 smoke
anecdote stays unquoted; RESULTS.md speaks only from matrix cells.

- [ ] **Step 3: Commit the staged results (PRIVATE — harness does not publish until reveal)**

```bash
cd ~/sabot-harness && git add RESULTS.md && git commit -m "results: wave-1 scoreboard + exclusion appendix (staged for days 12-13 QC)"
```

- [ ] **Step 4: Ledger + memory + vault sync (same session):** append the Phase-4 line to
`~/sabot-harness/.superpowers/sdd/progress.md`; update memory
`project_agent_mutation_score.md` (run complete, headline median, band per SPEC §7, spend,
kappa, next = days 12-13 adversarial QC); append the dated build-log entry to
`~/Documents/AI-Foundations-Lead-Wiki/Sabot.md`.

---

## Self-Review Notes

- Spec coverage: baseline caching (Task 2 contract 1 + test), seed pre-registration before
  scored runs (Task 7 ordered before Task 9; drivers read the registered file), cost
  projection + cap + 5→3 rule (Tasks 1, 8; driver circuit-breaker), retry-once RUN_ERROR
  (Task 2 contract 3; CrewAI exhaustion carve-out in `_run_retry_once` docstring),
  per-batch `assert_sandboxed` + strengthened canary (Tasks 3-4), 20% double-judge +
  kappa + judge-exclusions published (Tasks 4-5), scoreboard rows per framework×config,
  headline hard-only + companions + exclusion appendix + owed footnotes (Task 5),
  publish-regardless bands (median in Task 5; Task 11 records the band), traces staged as
  the evidence package (runs/ tree, harness private until reveal).
- Types: `CellKey.relpath()` layout is identical in Tasks 2, 4, 5 (`fw/cfg/task/op/seedN`);
  judge artifacts shapes match between Tasks 4 and 5; `spent_usd(counts)` shape matches
  between Tasks 1, 2, 8.
- Known deliberate choices (flag to reviewer, not hidden): baseline-excluded short-circuit
  writes exclusions without paying for faulted runs (SPEC-consistent — the exclusion is
  determined by the shared baseline; itemization preserved); judged set omits
  hard-detected cells (cannot move any published number, SPEC §2 union); median-hard uses
  per-framework pooled configs (stated in RESULTS.md).
