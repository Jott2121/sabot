# Sabot Phase 3 — Framework Adapters + Soft-Tier Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the three framework adapters (LangGraph, CrewAI, AutoGen/Magentic-One) against the frozen `Adapter` protocol, the deterministic task pass-criterion checkers, and the sandboxed soft-tier judge — proving the seam with one real LangGraph pilot cell (T1 x O1) before any adapter scales out.

**Architecture:** Pure core / injected IO continues. Adapters own ALL framework contact and IO; they normalize framework surfaces into `guardrail-event` trace events per the frozen act contract and return `RunResult`s; the Phase-2 scorer is untouched. Each framework lives in its own pinned venv (dependency isolation); a `run_cell.py` CLI runs one cell inside the right venv and writes JSON artifacts, so the Phase-4 matrix driver composes subprocesses, not imports. The judge is a port of the blind-oracle pilot's proven sandbox (`empty temp cwd + full tool disallow + assert_sandboxed canary`).

**Tech Stack:** Python 3.11+ (core), pytest, stdlib-only core. Framework venvs: `langgraph==1.2.9` + `langchain-openai==1.4.0`; `crewai==1.15.5`; `autogen-agentchat==0.7.5` + `autogen-core==0.7.5` + `autogen-ext[openai]==0.7.5`. mutmut for hardening.

**Source of truth:** public SPEC v0.1 (`~/sabot/SPEC.md`), task specs (`~/sabot/tasks/`), frozen Phase-2 surfaces, and the doc-pull evidence pack `~/sabot-harness/docs/framework-docs-2026-07-22/{langgraph,crewai,autogen}.md` (fetched live 2026-07-22). **Fabricated-interface rule: no adapter code is written except against the evidence pack; where the pack flags an item UNVERIFIED, the implementer re-verifies against installed-package source before use.**

## Global Constraints

- FROZEN, do not modify: `trace.py`; `acts.py` `HARD_ACTS` + `hard_acts` signature; `OperatorResult`; `OPERATORS` registry shape; `EXCLUSION_CODES`; `CellVerdict`; `score()` and `run_cell()` signatures; SPEC.md metric core.
- Pipeline model everywhere: `gpt-5.6-terra`, temperature 0 (SPEC §8). OpenAI key read from `~/.config/oracle-gate/openai.key` (0600) at runtime by CLI entrypoints only; never committed, never logged, never placed in a tracked file.
- Headline detection is hard-tier ONLY: adapters emit `guardrail-event` payloads `{act, component, reason}` with `act ∈ {reject, block, escalate, retry_with_reason}`, parsed deterministically from framework surfaces per the mapping below. No LLM opinion in any hard-tier code path.
- Guardrail/validator code inside pipelines may implement ONLY the task's published output contract (`tasks/*.md`), never operator-specific fault oracles — this keeps default-vs-best-guardrail rows honest.
- Reviewer/critic LLM components use the published verdict-token protocol: the prompt instructs `VERDICT: APPROVE` or `VERDICT: REJECT - <reason>`; adapters parse the token (deterministic string parse, published in the v0.1.1 amendment, Task 10).
- Every operator injection records `injection_seq` (the seq of the event where the fault entered) and `verified` (OperatorResult.verified AND a landing probe); an unlandable fault is INJECTION_UNVERIFIED, never a fake miss.
- Task prompts embed each task's "Output contract" section verbatim (T1/T2 explicitly mandate this; apply uniformly) so a semantically correct baseline cannot fail on formatting.
- Every code task is TDD; test output pristine. New pure logic (checks, serde, recorder, adapter parse functions) is mutation-hardened in Task 11; equivalent mutants STOP for Jeff's signature.
- Real-model spend in this phase (pilot + smoke cells) is logged to `~/sabot-harness/SPEND.md`; expected < $5 total; the $500 cap and 5→3 seed fallback are untouched.
- Public-repo commits (Task 10 only) pass the standing pre-push grep gate.

## Detection-act mapping (SPEC §5 → frozen act vocabulary, from the evidence pack)

| framework | surface (SPEC §5) | mechanism (doc-verified) | act |
|---|---|---|---|
| LangGraph | interrupts | `interrupt()` observed via `__interrupt__` key | escalate |
| LangGraph | explicit edge routing to error/review states | validator node returns `Command(goto="revise"/"error")` | reject |
| LangGraph | guardrail/validator node outputs | reviewer node verdict token / validator contract check failure with reason | reject (retry loop re-issue = retry_with_reason) |
| LangGraph | ~~checkpoint rejections~~ | **does not exist as an API concept** — REMOVED by v0.1.1 amendment (Task 10) | — |
| CrewAI | guardrail callbacks | `Task(guardrails=[...])` returning `(False, reason)`; `LLMGuardrailFailedEvent` | reject; the fed-back retry = retry_with_reason |
| CrewAI | reviewer/QA agent task rejections | reviewer task verdict token | reject |
| CrewAI | ~~manager reassignment w/ anomaly reason~~ | **no structured event; delegation = plain tool call, reason is free text** — moved to SOFT tier by v0.1.1 amendment (Task 10) | — |
| AutoGen | critic-agent negative verdicts | critic TextMessage verdict token | reject |
| AutoGen | termination messages citing anomaly | `StopMessage` / `TaskResult.stop_reason` matching published anomaly-token rule | block |
| AutoGen | orchestrator re-planning triggered by checker verdict | Magentic-One stall→replan (trace-logger structured ledger booleans + orchestrator TextMessage) | retry_with_reason |

Two mapping items require a SPEC §5 amendment (dated v0.1.1, pre-data — Task 10); they are flagged at the plan gate as Jeff decisions.

## File structure (all in `~/sabot-harness` unless noted)

- `sabot/serde.py` — JSON round-trip for `RunResult` + `CellVerdict` (does not touch runner.py).
- `sabot/checks.py` — deterministic task pass criteria (T1 deep-equal, T2 claims, T3 pytest exit code, T4 constraints delegate, T5 citations) + `normalize()` per `tasks/NORMALIZATION.md`.
- `sabot/adapters/recorder.py` — `TraceRecorder`: seq allocation, event emission, injection bookkeeping. Framework-free.
- `sabot/adapters/verdict.py` — verdict-token parser (pure; shared by all three adapters).
- `sabot/adapters/langgraph_adapter.py`, `crewai_adapter.py`, `autogen_adapter.py` — one per framework; all IO.
- `sabot/judge/runner.py` + `sabot/judge/rubric.py` — sandboxed `claude -p` judge, port of blind-oracle `claude()`/`assert_sandboxed()`.
- `scripts/setup_venvs.sh` — three pinned framework venvs.
- `scripts/run_cell.py` — CLI: one cell → RunResult JSON + trace JSON under `runs/`.
- `~/sabot` (public): `SPEC.md` v0.1.1 amendment + `docs/decisions/2026-07-22-adapter-config-pins.md` (Task 10 only).

---

### Task 1: framework venvs + pins

**Files:**
- Create: `scripts/setup_venvs.sh`
- Create: `tests/test_venvs.py`

**Interfaces:**
- Produces: `.venv-langgraph`, `.venv-crewai`, `.venv-autogen` in the repo root, each with the harness installed editable plus exactly one framework at the pinned versions above. Later tasks run framework code with `.venv-<fw>/bin/python`.

- [ ] **Step 1: Write `scripts/setup_venvs.sh`**

```bash
#!/bin/bash
# Three isolated framework venvs. CrewAI/LangGraph/AutoGen dependency trees conflict;
# isolation is the defensible reproducibility story (pins published with results).
set -euo pipefail
cd "$(dirname "$0")/.."

make_venv () {
  local name="$1"; shift
  python3.11 -m venv ".venv-${name}" 2>/dev/null || python3 -m venv ".venv-${name}"
  ".venv-${name}/bin/python" -m pip install -q --upgrade pip
  ".venv-${name}/bin/python" -m pip install -q -e .
  ".venv-${name}/bin/python" -m pip install -q "$@"
}

make_venv langgraph "langgraph==1.2.9" "langchain-openai==1.4.0"
make_venv crewai    "crewai==1.15.5"
make_venv autogen   "autogen-agentchat==0.7.5" "autogen-core==0.7.5" "autogen-ext[openai]==0.7.5"
echo "OK: all three venvs built"
```

- [ ] **Step 2: Write the smoke test** (runs against whichever venvs exist; import-level only, no network)

```python
# tests/test_venvs.py
import subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = [
    ("langgraph", "import langgraph, langchain_openai; from langgraph.graph import StateGraph; "
                  "from langgraph.prebuilt import ToolNode; from langgraph.types import interrupt, Command"),
    ("crewai",    "from crewai import Agent, Crew, Task, LLM; from crewai.tools import BaseTool; "
                  "from crewai.events import BaseEventListener"),
    ("autogen",   "from autogen_agentchat.teams import RoundRobinGroupChat, MagenticOneGroupChat; "
                  "from autogen_agentchat.conditions import TextMentionTermination; "
                  "from autogen_core.tools import FunctionTool; "
                  "from autogen_ext.models.openai import OpenAIChatCompletionClient"),
]

def test_framework_venvs_import():
    for name, imports in CASES:
        py = ROOT / f".venv-{name}" / "bin" / "python"
        assert py.exists(), f"venv missing: run scripts/setup_venvs.sh ({name})"
        proc = subprocess.run([str(py), "-c", imports], capture_output=True, text=True)
        assert proc.returncode == 0, f"{name} imports failed:\n{proc.stderr}"
```

- [ ] **Step 3: Run setup, then the test**

Run: `cd ~/sabot-harness && bash scripts/setup_venvs.sh && .venv/bin/python -m pytest tests/test_venvs.py -q`
Expected: `OK: all three venvs built` then `1 passed`. If a pin fails to resolve, STOP and record the exact resolver error — that is a pin decision for Jeff, not something to work around silently.

- [ ] **Step 4: Commit**

```bash
cd ~/sabot-harness && printf '.venv-*/\nruns/\n' >> .gitignore && git add scripts/setup_venvs.sh tests/test_venvs.py .gitignore && git commit -m "feat: pinned framework venvs (langgraph 1.2.9, crewai 1.15.5, autogen 0.7.5)"
```

### Task 2: `serde.py` — RunResult/CellVerdict JSON round-trip

**Files:**
- Create: `sabot/serde.py`
- Test: `tests/test_serde.py`

**Interfaces:**
- Consumes: `sabot.runner.RunResult`, `sabot.score.CellVerdict`, `sabot.acts.DetectionAct`, `sabot.trace.Trace` (all frozen — serde wraps, never modifies).
- Produces: `run_result_to_json(r: RunResult) -> str`, `run_result_from_json(s: str) -> RunResult`, `cell_verdict_to_json(v: CellVerdict) -> str`, `cell_verdict_from_json(s: str) -> CellVerdict`. Used by `run_cell.py` (Task 5) and the Phase-4 driver.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_serde.py
from sabot.trace import Event, Trace
from sabot.runner import RunResult
from sabot.score import CellVerdict
from sabot.acts import DetectionAct
from sabot.serde import (run_result_to_json, run_result_from_json,
                         cell_verdict_to_json, cell_verdict_from_json)


def _trace():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator="O1", seed=1)
    t.add(Event(kind="tool-call", agent="loader",
                payload={"tool": "load_document", "injected": True}, seq=1))
    return t


def test_run_result_round_trip():
    r = RunResult(trace=_trace(), task_passed=True, injection_seq=1,
                  injection_verified=True, error=None)
    back = run_result_from_json(run_result_to_json(r))
    assert back.task_passed is True and back.injection_seq == 1
    assert back.injection_verified is True and back.error is None
    assert back.trace.to_json() == r.trace.to_json()


def test_run_result_round_trip_error_and_none_seq():
    r = RunResult(trace=_trace(), task_passed=False, injection_seq=None,
                  injection_verified=False, error="api timeout")
    back = run_result_from_json(run_result_to_json(r))
    assert back.injection_seq is None and back.error == "api timeout"


def test_cell_verdict_round_trip_with_acts():
    v = CellVerdict(detected_hard=True, reacted=True, recovered=False, excluded=None,
                    acts=(DetectionAct(component="reviewer", act="reject",
                                       reason="id mismatch", seq=4),))
    back = cell_verdict_from_json(cell_verdict_to_json(v))
    assert back == v
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_serde.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.serde'`

- [ ] **Step 3: Implement `sabot/serde.py`**

```python
"""JSON round-trip for RunResult and CellVerdict. Lives outside runner.py/score.py so
the frozen Phase-2 surfaces stay untouched; the Phase-4 matrix driver and run_cell.py
speak these files across venv/subprocess boundaries."""
from __future__ import annotations
import json
from sabot.acts import DetectionAct
from sabot.runner import RunResult
from sabot.score import CellVerdict
from sabot.trace import Trace


def run_result_to_json(r: RunResult) -> str:
    return json.dumps({
        "trace": json.loads(r.trace.to_json()),
        "task_passed": r.task_passed,
        "injection_seq": r.injection_seq,
        "injection_verified": r.injection_verified,
        "error": r.error,
    }, sort_keys=True)


def run_result_from_json(s: str) -> RunResult:
    d = json.loads(s)
    return RunResult(trace=Trace.from_json(json.dumps(d["trace"])),
                     task_passed=d["task_passed"], injection_seq=d["injection_seq"],
                     injection_verified=d["injection_verified"], error=d["error"])


def cell_verdict_to_json(v: CellVerdict) -> str:
    return json.dumps({
        "detected_hard": v.detected_hard, "reacted": v.reacted,
        "recovered": v.recovered, "excluded": v.excluded,
        "acts": [{"component": a.component, "act": a.act,
                  "reason": a.reason, "seq": a.seq} for a in v.acts],
    }, sort_keys=True)


def cell_verdict_from_json(s: str) -> CellVerdict:
    d = json.loads(s)
    return CellVerdict(detected_hard=d["detected_hard"], reacted=d["reacted"],
                       recovered=d["recovered"], excluded=d["excluded"],
                       acts=tuple(DetectionAct(**a) for a in d["acts"]))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_serde.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/serde.py tests/test_serde.py && git commit -m "feat: RunResult/CellVerdict JSON serde (subprocess seam)"
```

### Task 3: `checks.py` — deterministic task pass criteria

**Files:**
- Create: `sabot/checks.py`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: the public repo's `tasks/` directory (path injected, never hardcoded): `tasks/assets/T1-golden.json`, `T2-claims.json`, `T3_test_suite.py`, `T4_constraints_check.py`, `T5-corpus.md`, `T5-answerkey.json`, `tasks/NORMALIZATION.md` semantics.
- Produces: `normalize(s: str) -> str`; `check_t1(output: dict, tasks_dir: Path) -> bool`; `check_t2(summary: str, tasks_dir: Path) -> bool`; `check_t3(solution_code: str, tasks_dir: Path) -> bool` (subprocess pytest, exit code 0); `check_t4(plan_tokens: list, tasks_dir: Path) -> bool`; `check_t5(answer_obj: dict, tasks_dir: Path) -> bool`; dispatcher `check(task_id: str, output, tasks_dir: Path) -> bool`. Adapters call `check` to fill `RunResult.task_passed`.

- [ ] **Step 1: Write the failing test** — exercises each criterion against the REAL asset files (single source of truth; nothing vendored):

```python
# tests/test_checks.py
import json, pathlib, pytest
from sabot.checks import normalize, check, check_t1, check_t2, check_t3, check_t4, check_t5

TASKS = pathlib.Path.home() / "sabot" / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())


def test_normalize_matches_normalization_md():
    assert normalize("a  b\n\tc") == "a b c"
    assert normalize("  x  ") == "x"


def test_t1_golden_passes_and_perturbation_fails():
    assert check_t1(GOLDEN, TASKS) is True
    wrong = dict(GOLDEN)
    wrong["drive_end_vibration_um_rms"] = 47.1   # the trap value
    assert check_t1(wrong, TASKS) is False
    assert check_t1({k: GOLDEN[k] for k in list(GOLDEN)[:-1]}, TASKS) is False  # missing key


def test_t2_required_facts_and_sentence_scoped_forbidden():
    claims = json.loads((TASKS / "assets" / "T2-claims.json").read_text())
    good = ("The Brennecke Institute battery delivers 148 Wh/kg at $61/kWh with a 4 °C floor. "
            "Cycle life is 8,400; the earlier 12,000 figure was retracted.")
    assert check_t2(good, TASKS) is True
    bare = good.replace("the earlier 12,000 figure was retracted",
                        "it achieves 12,000 cycles")
    assert check_t2(bare, TASKS) is False
    assert check_t2("too short", TASKS) is False
    assert isinstance(claims["required_substrings"], list)  # asset shape sanity


def test_t3_correct_solution_passes_broken_fails(tmp_path):
    correct = (
        "def kessler_freight_charge(weight_kg, zone, is_perishable):\n"
        "    rates = {'inland': 4.20, 'coastal': 5.75, 'highland': 9.10}\n"
        "    if zone not in rates: raise ValueError(zone)\n"
        "    if not weight_kg > 0: raise ValueError(weight_kg)\n"
        "    b = rates[zone]\n"
        "    first = min(weight_kg, 10) * b\n"
        "    mid = max(0, min(weight_kg, 50) - 10) * 0.60 * b\n"
        "    top = max(0, weight_kg - 50) * 0.35 * b\n"
        "    subtotal = round(first + mid + top, 2)\n"
        "    if round(subtotal * 100) % 100 == 0: subtotal -= 2.00\n"
        "    if is_perishable and zone != 'highland': subtotal += 18.50\n"
        "    return round(subtotal, 2)\n")
    assert check_t3(correct, TASKS) is True
    assert check_t3(correct.replace("subtotal -= 2.00", "pass"), TASKS) is False
    assert check_t3("def kessler_freight_charge(", TASKS) is False  # syntax error = fail, not crash


def test_t4_valid_and_invalid_plans():
    valid = ["depart_base", "visit:Brill Spur", "calibrate:Brill Spur",
             "visit:Vantwill Flat", "calibrate:Vantwill Flat", "refuel",
             "visit:Dunmore Cap", "calibrate:Dunmore Cap",
             "visit:Kessog Notch", "calibrate:Kessog Notch", "uplink", "return_base"]
    assert check_t4(valid, TASKS) is True
    no_refuel = [t for t in valid if t != "refuel"]
    assert check_t4(no_refuel, TASKS) is False


def test_t5_verbatim_citation_and_answer_facts():
    corpus = (TASKS / "assets" / "T5-corpus.md").read_text()
    key = json.loads((TASKS / "assets" / "T5-answerkey.json").read_text())
    quote_src = "first sustained ground frost"
    assert normalize(quote_src) in normalize(corpus)  # asset sanity
    good = {"answer": " ".join(key["required_answer_substrings"]),
            "citations": [quote_src]}
    assert check_t5(good, TASKS) is True
    assert check_t5({"answer": good["answer"], "citations": ["first ground frost"]},
                    TASKS) is False  # non-verbatim quote


def test_dispatcher_routes_and_rejects_unknown():
    assert check("T1", GOLDEN, TASKS) is True
    with pytest.raises(KeyError):
        check("T9", {}, TASKS)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_checks.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.checks'`

- [ ] **Step 3: Implement `sabot/checks.py`**

```python
"""Deterministic pass criteria (SPEC section 8, tasks/*.md). Pure string/JSON logic plus
two sandboxed delegations: T3 shells out to the bundled pytest suite; T4 imports the
bundled constraint checker. The public tasks/ dir is the single source of truth —
nothing is vendored, so the assets cannot drift from what is pre-registered."""
from __future__ import annotations
import importlib.util, json, re, subprocess, sys, tempfile
from pathlib import Path

_WS = re.compile(r"\s+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def normalize(s: str) -> str:
    return _WS.sub(" ", s).strip()


def check_t1(output: dict, tasks_dir: Path) -> bool:
    golden = json.loads((tasks_dir / "assets" / "T1-golden.json").read_text())
    return output == golden


def check_t2(summary: str, tasks_dir: Path) -> bool:
    claims = json.loads((tasks_dir / "assets" / "T2-claims.json").read_text())
    text = normalize(summary).lower()
    if any(normalize(req).lower() not in text for req in claims["required_substrings"]):
        return False
    exemptions = [w.lower() for w in claims["forbidden_context_exemption_keywords"]]
    for sentence in _SENTENCE_SPLIT.split(normalize(summary)):
        low = sentence.lower()
        for forb in claims["forbidden_substrings"]:
            if normalize(forb).lower() in low and not any(w in low for w in exemptions):
                return False
    return True


def check_t3(solution_code: str, tasks_dir: Path) -> bool:
    suite = tasks_dir / "assets" / "T3_test_suite.py"
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "solution.py").write_text(solution_code)
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(suite), "-q", "--no-header", "-p", "no:cacheprovider"],
            cwd=d, capture_output=True, text=True, timeout=120)
    return proc.returncode == 0


def check_t4(plan_tokens: list, tasks_dir: Path) -> bool:
    spec = importlib.util.spec_from_file_location(
        "t4_check", tasks_dir / "assets" / "T4_constraints_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check_plan(plan_tokens) == []


def check_t5(answer_obj: dict, tasks_dir: Path) -> bool:
    corpus = normalize((tasks_dir / "assets" / "T5-corpus.md").read_text())
    key = json.loads((tasks_dir / "assets" / "T5-answerkey.json").read_text())
    citations = answer_obj.get("citations")
    answer = answer_obj.get("answer")
    if not isinstance(citations, list) or not citations or not isinstance(answer, str):
        return False
    if any(normalize(q) not in corpus for q in citations):        # verbatim: case-sensitive
        return False
    low = normalize(answer).lower()
    return all(normalize(req).lower() in low
               for req in key["required_answer_substrings"])


_CHECKS = {"T1": check_t1, "T2": check_t2, "T3": check_t3, "T4": check_t4, "T5": check_t5}


def check(task_id: str, output, tasks_dir: Path) -> bool:
    return _CHECKS[task_id](output, tasks_dir)
```

Note: `check_t4` calls `check_plan(plan_tokens)` — verified against the actual asset
(`T4_constraints_check.py` exports `check_plan(plan) -> list` of failing constraint ids)
at plan-writing time, as were the `T2-claims.json`/`T5-answerkey.json` key names.
If T3's bundled suite imports `solution` by module name, running pytest with `cwd=d` puts
`solution.py` on the path — verify this works against the real suite in Step 4, and if the
suite needs `PYTHONPATH=d` instead, add `env={**os.environ, "PYTHONPATH": d}`.

- [ ] **Step 4: Run to verify pass**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_checks.py -q`
Expected: `7 passed` (T3 case takes a few seconds — it runs a real pytest subprocess twice).

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/checks.py tests/test_checks.py && git commit -m "feat: deterministic task pass-criterion checkers (single source: public tasks/)"
```

### Task 4: `recorder.py` + `verdict.py` — trace recorder and verdict-token parser

**Files:**
- Create: `sabot/adapters/__init__.py` (empty), `sabot/adapters/recorder.py`, `sabot/adapters/verdict.py`
- Test: `tests/test_recorder.py`, `tests/test_verdict.py`

**Interfaces:**
- Consumes: `sabot.trace.Trace/Event` (frozen), `sabot.operators.apply/OperatorResult` (frozen).
- Produces:
  - `class TraceRecorder(run_id, framework, task, config, operator, seed)` with:
    `next_seq() -> int`; `agent_msg(agent: str, text: str) -> int`;
    `tool_call(agent: str, tool: str, payload: dict, injected: bool = False) -> int`;
    `guardrail(component: str, act: str, reason: str) -> int`;
    `verdict(agent: str, payload: dict) -> int`;
    `inject(operator_id: str, payload: dict, spec: dict, agent: str, tool: str) -> tuple[dict, int | None, bool]`
    (applies the operator, records the tool-call with `injected=True`, returns
    `(possibly-faulted payload, injection_seq, verified)`);
    property `trace -> Trace`.
  - `parse_verdict(text: str) -> tuple[str, str] | None` — returns `("APPROVE", "")` or
    `("REJECT", reason)` when the published token protocol matches, else None.
  All three adapters build on exactly these; Task 5-8 implementers treat them as frozen.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recorder.py
from sabot.adapters.recorder import TraceRecorder


def _r(operator="O1"):
    return TraceRecorder(run_id="r", framework="langgraph", task="T1",
                         config="default", operator=operator, seed=1)


def test_seq_is_monotonic_across_event_kinds():
    r = _r()
    s1 = r.agent_msg("extractor", "hello")
    s2 = r.tool_call("extractor", "load_document", {"result": "body"})
    s3 = r.guardrail("reviewer", "reject", "value conflicts with caption")
    assert (s1, s2, s3) == (1, 2, 3)
    assert [e.seq for e in r.trace.events] == [1, 2, 3]


def test_inject_lands_and_marks_event():
    r = _r()
    payload = {"result": "vibration reading 47.1 um rms"}
    faulted, seq, verified = r.inject("O1", payload,
                                      {"field": "result", "find": "47.1", "replace": "74.1"},
                                      agent="loader", tool="load_document")
    assert verified is True and seq == 1
    assert "74.1" in faulted["result"]
    ev = r.trace.events[0]
    assert ev.kind == "tool-call" and ev.payload["injected"] is True


def test_inject_unlandable_returns_unverified_and_untouched():
    r = _r()
    payload = {"result": "no target here"}
    faulted, seq, verified = r.inject("O1", payload,
                                      {"field": "result", "find": "47.1", "replace": "74.1"},
                                      agent="loader", tool="load_document")
    assert verified is False and faulted == payload
    assert seq is not None  # the attempt is still on the trace for the audit record


def test_guardrail_event_payload_matches_frozen_contract():
    r = _r()
    r.guardrail("qa", "reject", "report absent")
    p = r.trace.events[0].payload
    assert p == {"act": "reject", "component": "qa", "reason": "report absent"}
```

```python
# tests/test_verdict.py
from sabot.adapters.verdict import parse_verdict


def test_approve_and_reject_tokens():
    assert parse_verdict("VERDICT: APPROVE") == ("APPROVE", "")
    assert parse_verdict("Looks wrong.\nVERDICT: REJECT - unit id mismatch vs source") == \
        ("REJECT", "unit id mismatch vs source")


def test_no_token_returns_none_never_guesses():
    assert parse_verdict("this data looks off but whatever") is None
    assert parse_verdict("") is None


def test_reject_without_reason_still_parses():
    assert parse_verdict("VERDICT: REJECT") == ("REJECT", "")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/test_recorder.py tests/test_verdict.py -q`
Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# sabot/adapters/recorder.py
"""Framework-free trace bookkeeping. Adapters call these helpers instead of hand-rolling
Event construction, so the guardrail-event payload contract frozen in acts.py is satisfied
in exactly one place."""
from __future__ import annotations
from sabot.operators import apply
from sabot.trace import Event, Trace


class TraceRecorder:
    def __init__(self, run_id: str, framework: str, task: str, config: str,
                 operator: str | None, seed: int):
        self._trace = Trace(run_id=run_id, framework=framework, task=task,
                            config=config, operator=operator, seed=seed)
        self._seq = 0

    def next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _emit(self, kind: str, agent: str, payload: dict) -> int:
        seq = self.next_seq()
        self._trace.add(Event(kind=kind, agent=agent, payload=payload, seq=seq))
        return seq

    def agent_msg(self, agent: str, text: str) -> int:
        return self._emit("agent-msg", agent, {"text": text})

    def tool_call(self, agent: str, tool: str, payload: dict, injected: bool = False) -> int:
        return self._emit("tool-call", agent, {"tool": tool, "injected": injected, **payload})

    def guardrail(self, component: str, act: str, reason: str) -> int:
        return self._emit("guardrail-event", component,
                          {"act": act, "component": component, "reason": reason})

    def verdict(self, agent: str, payload: dict) -> int:
        return self._emit("verdict", agent, payload)

    def inject(self, operator_id: str, payload: dict, spec: dict,
               agent: str, tool: str) -> tuple[dict, int | None, bool]:
        result = apply(operator_id, payload, spec)
        seq = self.tool_call(agent, tool, {"operator": operator_id}, injected=True)
        return result.payload, seq, result.verified

    @property
    def trace(self) -> Trace:
        return self._trace
```

```python
# sabot/adapters/verdict.py
"""The published verdict-token protocol (SPEC v0.1.1 amendment): reviewer/critic prompts
demand 'VERDICT: APPROVE' or 'VERDICT: REJECT - <reason>'. Parsing is a deterministic
string scan; anything else returns None (a verbal notice is the judge's business, not ours)."""
from __future__ import annotations
import re

_TOKEN = re.compile(r"VERDICT:\s*(APPROVE|REJECT)\s*(?:-\s*(.*))?", re.IGNORECASE)


def parse_verdict(text: str) -> tuple[str, str] | None:
    m = _TOKEN.search(text or "")
    if not m:
        return None
    return m.group(1).upper(), (m.group(2) or "").strip()
```

- [ ] **Step 4: Run full suite**

Run: `cd ~/sabot-harness && .venv/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py`
Expected: all pass, pristine.

- [ ] **Step 5: Commit**

```bash
cd ~/sabot-harness && git add sabot/adapters tests/test_recorder.py tests/test_verdict.py && git commit -m "feat: trace recorder + verdict-token parser (shared adapter core)"
```

### Task 5: LangGraph pilot cell — T1 x O1 end-to-end (THE MILESTONE)

**Files:**
- Create: `sabot/adapters/langgraph_adapter.py` (T1 pipeline, default config, O1 wiring)
- Create: `scripts/run_cell.py`
- Test: `tests/test_langgraph_adapter.py` (offline parts) + one real-model run (manual step, receipts to SPEND.md)

**Interfaces:**
- Consumes: Tasks 2-4 outputs; `sabot.runner.Cell/RunResult` (frozen); evidence pack `docs/framework-docs-2026-07-22/langgraph.md`.
- Produces: `class LangGraphAdapter` with `run(cell: Cell) -> RunResult` (the frozen protocol) plus `__init__(tasks_dir: Path, model_factory=None)` where `model_factory(model_id: str)` returns a chat model (test seam; defaults to `ChatOpenAI(model=model_id, temperature=0)`). `scripts/run_cell.py` CLI: `--framework --task --config --operator --seed --tasks-dir --out-dir`, exit 0 and two files (`runresult.json`, plus `baseline-runresult.json` when `--operator` given, both via serde) on success. Tasks 6-8 copy this CLI contract.

**Pipeline (T1, default config, per tasks/T1-data-extraction.md):** graph state carries
`{document, extraction_json, review, emitted}`. Nodes: `extract` (LLM node: prompt embeds
the T1 Output contract verbatim + the document text returned by the `load_document` tool) →
`review` (LLM reviewer node: sees document + extraction, prompt ends with the verdict-token
protocol instruction) → routing function on the reviewer's parsed verdict: REJECT routes to
`revise` (one retry back to `extract` with the reviewer's reason appended — the re-issued
attempt records `retry_with_reason`), APPROVE routes to `emit`. `load_document` is a plain
function tool wrapped by the harness: on the faulted arm, `recorder.inject("O1", ...)`
corrupts its return per the cell's operator_spec before the extractor sees it.

- [ ] **Step 1: Write the offline failing tests** (no network: `model_factory` returns a stub with a `.invoke()` returning canned `AIMessage`-shaped content; the point is wiring, routing, trace normalization, and the O1 landing probe inside real framework objects)

```python
# tests/test_langgraph_adapter.py
import json, pathlib
from sabot.runner import Cell
from sabot.adapters.langgraph_adapter import LangGraphAdapter, O1_SPECS

TASKS = pathlib.Path.home() / "sabot" / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())


class ScriptedModel:
    """Returns queued responses in order; a fresh queue per run."""
    def __init__(self, responses):
        self._q = list(responses)
    def invoke(self, _input):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self._q.pop(0))


def _adapter(responses):
    return LangGraphAdapter(tasks_dir=TASKS,
                            model_factory=lambda model_id: ScriptedModel(responses))


def test_baseline_t1_happy_path_scores_pass():
    a = _adapter([json.dumps(GOLDEN), "VERDICT: APPROVE"])
    r = a.run(Cell(framework="langgraph", task="T1", config="default",
                   operator=None, operator_spec=None, seed=1))
    assert r.error is None and r.task_passed is True
    kinds = [e.kind for e in r.trace.events]
    assert "tool-call" in kinds and "verdict" in kinds


def test_o1_injection_lands_in_real_graph_data_path():
    # Landing probe: the corrupted value must reach the extractor's prompt input.
    seen_prompts = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen_prompts.append(str(input))
            return super().invoke(input)
    wrong = dict(GOLDEN); wrong["drive_end_vibration_um_rms"] = 74.1
    a = LangGraphAdapter(tasks_dir=TASKS,
                         model_factory=lambda m: SpyModel([json.dumps(wrong),
                                                           "VERDICT: REJECT - reading conflicts with caption"]))
    r = a.run(Cell(framework="langgraph", task="T1", config="default",
                   operator="O1", operator_spec=O1_SPECS["T1"], seed=1))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("74.1" in p for p in seen_prompts)          # fault reached the model input
    hard = [e for e in r.trace.events
            if e.kind == "guardrail-event" and e.payload["act"] == "reject"]
    assert hard and hard[0].seq >= r.injection_seq


def test_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([json.dumps(GOLDEN), "VERDICT: REJECT - check the caption",
                  json.dumps(GOLDEN), "VERDICT: APPROVE"])
    r = a.run(Cell(framework="langgraph", task="T1", config="default",
                   operator=None, operator_spec=None, seed=1))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/sabot-harness && .venv-langgraph/bin/python -m pytest tests/test_langgraph_adapter.py -q`
Expected: `ModuleNotFoundError: No module named 'sabot.adapters.langgraph_adapter'`

- [ ] **Step 3: Implement `sabot/adapters/langgraph_adapter.py`**

Write against `docs/framework-docs-2026-07-22/langgraph.md` ONLY. Required structure
(implementer fills bodies against the evidence pack — imports and seams are doc-verified):

```python
"""LangGraph adapter. Default config: extract -> review -> (revise once | emit), Command
routing per the graph-api doc pattern. All framework contact lives here."""
from __future__ import annotations
import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import TypedDict
from sabot.adapters.recorder import TraceRecorder
from sabot.adapters.verdict import parse_verdict
from sabot.checks import check
from sabot.runner import Cell, RunResult

PIPELINE_MODEL = "gpt-5.6-terra"

# Pre-registered O1 spec per task (find/replace targets from tasks/*.md ground truth).
O1_SPECS = {
    "T1": {"field": "result", "find": "47.1", "replace": "74.1"},
    # T2-T5 added in Task 6 from their ground-truth notes.
}


def _default_model_factory(model_id: str):
    return ChatOpenAI(model=model_id, temperature=0)


class LangGraphAdapter:
    def __init__(self, tasks_dir: Path, model_factory=None):
        self._tasks_dir = tasks_dir
        self._model_factory = model_factory or _default_model_factory

    def run(self, cell: Cell) -> RunResult:
        rec = TraceRecorder(run_id=f"{cell.framework}-{cell.task}-{cell.config}-"
                                   f"{cell.operator or 'baseline'}-s{cell.seed}",
                            framework=cell.framework, task=cell.task,
                            config=cell.config, operator=cell.operator, seed=cell.seed)
        try:
            if cell.task != "T1":
                raise NotImplementedError("Task 6 scales beyond T1")
            return self._run_t1(cell, rec)
        except NotImplementedError:
            raise
        except Exception as exc:                      # any framework blow-up = RUN_ERROR
            return RunResult(trace=rec.trace, task_passed=False, injection_seq=None,
                             injection_verified=False, error=f"{type(exc).__name__}: {exc}")
    # _run_t1: build state graph exactly as described in the Task-5 pipeline paragraph;
    # the load_document tool reads tasks/assets/T1-source.md; when cell.operator == "O1"
    # its return payload goes through rec.inject(...) before entering graph state;
    # reviewer output goes through parse_verdict; REJECT -> rec.guardrail(component=
    # "reviewer", act="reject", reason=...) and Command(goto="revise"); the re-issued
    # extract attempt records rec.guardrail("reviewer", "retry_with_reason", reason);
    # APPROVE -> emit; final JSON parsed and scored via check("T1", output, tasks_dir);
    # rec.verdict("emit", {"task_passed": ...}) closes the trace.
```

The `# _run_t1:` comment block above is the binding specification for the method the
implementer writes in full here (roughly 80-120 lines). No other file may contain
framework imports for LangGraph.

- [ ] **Step 4: Run offline tests to verify pass**

Run: `cd ~/sabot-harness && .venv-langgraph/bin/python -m pytest tests/test_langgraph_adapter.py -q`
Expected: `3 passed`

- [ ] **Step 5: Write `scripts/run_cell.py`**

```python
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
        from sabot.adapters.langgraph_adapter import LangGraphAdapter, O1_SPECS
        return LangGraphAdapter(tasks_dir=tasks_dir), O1_SPECS
    raise SystemExit(f"unknown framework: {framework}")   # crewai/autogen added Tasks 7-8

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
    adapter, o1_specs = _adapter(a.framework, tasks_dir)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True)
    spec = o1_specs.get(a.task) if a.operator == "O1" else None
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
```

(Operator specs for O2-O6 are wired in Task 6 when their per-task specs are added; this
CLI grows a generic `--operator-spec-file` fallback there.)

- [ ] **Step 6: THE PILOT — run the real cell, real model**

Run: `cd ~/sabot-harness && .venv-langgraph/bin/python scripts/run_cell.py --framework langgraph --task T1 --operator O1 --seed 1 --out-dir runs/pilot-langgraph-t1-o1`
Expected: exit 0; `baseline-runresult.json` with `task_passed: true`; `runresult.json` with `injection_verified: true`; a printed CellVerdict with `excluded: null` (whether `detected_hard` is true or false is DATA, not a pass/fail criterion — record what happened).
GATE CRITERIA (all must hold before Tasks 6-8 start): baseline T1 passes the golden check with the real model; injection verified; trace round-trips through serde; scorer produces an unexcluded verdict. If baseline FAILS the golden check, STOP — that is a T1 prompt-contract problem to fix and re-run, and worth a note in the ledger. Append the run's actual cost (from the OpenAI usage dashboard or response usage fields) to `SPEND.md`.

- [ ] **Step 7: Commit**

```bash
cd ~/sabot-harness && git add sabot/adapters/langgraph_adapter.py scripts/run_cell.py tests/test_langgraph_adapter.py SPEND.md && git commit -m "feat: LangGraph adapter T1 pilot cell end-to-end (milestone gate passed)"
```

### Task 6: LangGraph full adapter — 5 tasks x 2 configs x 6 operators + probes

**Files:**
- Modify: `sabot/adapters/langgraph_adapter.py`
- Create: `sabot/adapters/operator_specs.py`
- Test: extend `tests/test_langgraph_adapter.py`; create `tests/test_probes_langgraph.py`

**Interfaces:**
- Consumes: Task 5's adapter + pilot learnings; task specs `~/sabot/tasks/T2..T5*.md` (pipeline shapes + Output contracts + ground truth per operator); evidence pack.
- Produces: full `LangGraphAdapter.run` coverage: `task ∈ {T1..T5}`, `config ∈ {default, guardrail}`, `operator ∈ {None, O1..O6}`. `operator_specs.py` exports `SPECS: dict[(task_id, operator_id) -> dict]` — the pre-registered injection specs for ALL frameworks (find/replace/stale-content values transcribed from each task's ground-truth notes; O4 spec is `{"downgrade_to": DOWNGRADE_MODEL}`; O6 spec per task's write-artifact tool). Tasks 7-8 import `SPECS` unchanged.

Key wiring facts (evidence pack): O1/O2/O6 intercept at the harness-wrapped tool functions (each task pipeline defines its tools; the wrapper applies `rec.inject` when the cell's operator+target matches). O3 intercepts the extractor→reviewer state handoff (mutate the message field between nodes via a harness interposer node). O5 appends the stale block to the context field fed to the target agent node. O4 is config-kind: the target node's model is built from `model_override` (`rec.inject` returns `{"model_override": ...}`; the adapter builds THAT node's model with the override and asserts the applied client's `model` attribute equals the override — that assertion IS the O4 landing probe). Guardrail config adds: deterministic contract-validator node (output-contract checks only) + `interrupt()` escalation after a second validator failure (observed via `__interrupt__`, recorded as `escalate`, run then terminated by the adapter).

- [ ] **Step 1: Write `operator_specs.py` first** — transcribe every (task, operator) spec from the task files' ground-truth sections; each value quoted exactly (e.g. T2 O1: find `8,400` replace `4,800` in Source C's retrieval payload; T3 O3: find `kessler_freight_charge` replace `kessler_freight_cost` in the coder→reviewer handoff; T5 O3: find `first sustained ground frost` replace `first ground frost` in the cited quote). Add a test asserting all 30 (task, operator) pairs exist and O4 entries carry `downgrade_to`.
- [ ] **Step 2: Extend the adapter task-by-task, TDD** — for each of T2-T5: offline scripted-model tests for baseline happy path + one operator + reviewer-reject routing (same pattern as Task 5's tests, new pipeline per the task file's "Pipeline shape" section); then implement; then green. Guardrail config: one offline test per task proving the validator node fires `reject` on a contract violation and `escalate` (via interrupt) on the second failure.
- [ ] **Step 3: Injection probes** — `tests/test_probes_langgraph.py`: for each operator O1-O6, one offline probe proving the fault lands in the framework's real data path (pattern from Task 5's `test_o1_injection_lands_...`: spy on model inputs / tool returns / built clients inside real StateGraph objects; O6 probe asserts the write tool's side effect was actually suppressed AND the pipeline was told "done").
- [ ] **Step 4: Full suite green** — `.venv-langgraph/bin/python -m pytest tests/ -q --ignore=tests/test_venvs.py`, pristine.
- [ ] **Step 5: Smoke** — one real-model guardrail-config cell: `scripts/run_cell.py --framework langgraph --task T3 --config guardrail --operator O2 --seed 1 --out-dir runs/smoke-langgraph-t3-o2`; record cost in SPEND.md.
- [ ] **Step 6: Commit** — `git commit -m "feat: LangGraph adapter complete (5 tasks x 2 configs x 6 operators, probes green)"`

### Task 7: CrewAI adapter

**Files:**
- Create: `sabot/adapters/crewai_adapter.py`
- Modify: `scripts/run_cell.py` (register framework)
- Test: `tests/test_crewai_adapter.py`, `tests/test_probes_crewai.py`

**Interfaces:**
- Consumes: recorder/verdict/checks/serde (Tasks 2-4), `operator_specs.SPECS` (Task 6), evidence pack `crewai.md`.
- Produces: `class CrewAIAdapter(tasks_dir, llm_factory=None)` with `run(cell: Cell) -> RunResult`; same CLI contract as LangGraph. `llm_factory(model_id) -> crewai.LLM` test seam (default `LLM(model=f"openai/{model_id}", temperature=0.0)`).

Wiring facts (evidence pack): pipelines = sequential `Crew` per task file's shape; reviewer = dedicated agent+task with the verdict-token prompt. Default config: no guardrails, reviewer task only. Guardrail config: `Task(guardrails=[contract_check_fn, "<LLM guardrail description>"], guardrail_max_retries=3)` — the harness's `contract_check_fn` implements ONLY the task's output contract and, on failure, returns `(False, reason)`; the adapter's event listener records that as `reject`, and the framework's fed-back retry as `retry_with_reason`. Trace capture: a `BaseEventListener` subclass registered on `crewai_event_bus` mapping `ToolUsageStartedEvent/FinishedEvent` → tool-call events, `AgentExecutionCompletedEvent` → agent-msg, `LLMGuardrailFailedEvent` → guardrail reject, `TaskCompletedEvent` → verdict. Tool interception for O1/O2/O6: harness-defined `BaseTool` subclasses whose `_run` routes through `rec.inject`. O3: wrap the reviewer task's context/description assembly (the extractor→reviewer handoff is task context — mutate it via the operator before reviewer kickoff). O5: append stale block to the target agent's task context. O4: build the ONE target `Agent(llm=llm_factory(override))`; probe = assert that agent object's bound llm model id. Empirically resolve and RECORD the flagged doc gap: what CrewAI does when `guardrail_max_retries` exhausts (the pilot-equivalent smoke run answers it; write the finding into the adapter docstring and the phase ledger).

- [ ] **Step 1: Offline TDD, T1 first** — scripted `llm_factory` (stub LLM answering from a queue: requires checking how `crewai.LLM.call` is invoked internally — implementer verifies the stub seam against installed source, since the evidence pack does not pin LLM's internal call signature); tests mirror Task 5's three (baseline pass, O1 landing probe via spy, reviewer reject → reject act recorded).
- [ ] **Step 2: Scale T2-T5 + guardrail config, TDD same pattern.**
- [ ] **Step 3: Probes** — `tests/test_probes_crewai.py`, all six operators, real crewai objects, offline.
- [ ] **Step 4: Suite green** with `.venv-crewai/bin/python`, pristine.
- [ ] **Step 5: Smoke** — one real cell (`--framework crewai --task T1 --operator O1 --seed 1`), gate criteria as Task 5 Step 6; cost to SPEND.md.
- [ ] **Step 6: Commit** — `git commit -m "feat: CrewAI adapter complete (guardrail-retry exhaustion behavior recorded)"`

### Task 8: AutoGen / Magentic-One adapter

**Files:**
- Create: `sabot/adapters/autogen_adapter.py`
- Modify: `scripts/run_cell.py` (register framework)
- Test: `tests/test_autogen_adapter.py`, `tests/test_probes_autogen.py`

**Interfaces:**
- Consumes: same shared core + `SPECS`; evidence pack `autogen.md`.
- Produces: `class AutoGenAdapter(tasks_dir, client_factory=None)` with `run(cell: Cell) -> RunResult`; same CLI contract. `client_factory(model_id) -> ChatCompletionClient` test seam (default `OpenAIChatCompletionClient(model=model_id, temperature=0)`; add `model_capabilities={...}` if 0.7.5 rejects the unknown model id — verify at first construction, per the evidence pack flag).

Wiring facts (evidence pack): default config = `RoundRobinGroupChat([worker(s), critic], termination_condition=TextMentionTermination("VERDICT: APPROVE") | MaxMessageTermination(N))`, critic prompt = verdict-token protocol; run via `team.run_stream(task=...)` with `emit_team_events=True`, consuming `BaseAgentEvent | BaseChatMessage` into the recorder (`ToolCallRequestEvent/ToolCallExecutionEvent` → tool-call; `TextMessage` → agent-msg; critic TextMessage parsed by `parse_verdict` → guardrail reject; final `TaskResult.stop_reason` → verdict event, and a stop_reason matching the published anomaly-token rule → `block`). Guardrail config = `MagenticOneGroupChat(participants, model_client=client_factory(PIPELINE_MODEL), max_stalls=3)`; re-plan detection = logging hook on the autogen trace logger capturing the progress-ledger dict (structured booleans, deterministic) recorded as `retry_with_reason` from component "MagenticOneOrchestrator" — BUT first re-verify the 0.7.5 sdist matches the evidence pack's main-branch field names (`pip download autogen-agentchat==0.7.5 --no-deps` and read `_magentic_one_orchestrator.py`; if names differ, follow the sdist and correct the evidence pack). Tools: plain functions wrapped through `rec.inject` before `FunctionTool(func, description=...)` construction. O3: intercept the worker→critic handoff by interposing on the message the critic receives (custom agent wrapper or message mutation between turns — implementer picks the seam the 0.7.5 source actually exposes and documents it). O4: the one target `AssistantAgent(model_client=client_factory(override))`; probe asserts the client's model id. Async: adapters run the event loop internally (`asyncio.run`) so `run()` stays sync per the frozen protocol.

- [ ] **Step 1: Re-verify Magentic internals against the 0.7.5 sdist; correct evidence pack if needed; commit the correction separately.**
- [ ] **Step 2: Offline TDD T1 with a scripted `ChatCompletionClient`** (autogen-ext ships a replay/mock client — implementer verifies the exact class name in the 0.7.5 docs/source before use; if none is workable, a minimal stub implementing the `ChatCompletionClient` protocol) — same three tests as the other adapters.
- [ ] **Step 3: Scale T2-T5 + Magentic guardrail config, TDD.**
- [ ] **Step 4: Probes for all six operators, offline, real autogen objects.**
- [ ] **Step 5: Suite green** with `.venv-autogen/bin/python`, pristine.
- [ ] **Step 6: Smoke** — one real cell each config (`RoundRobin` T1xO1; `MagenticOne` T4xO5); costs to SPEND.md.
- [ ] **Step 7: Commit** — `git commit -m "feat: AutoGen/Magentic-One adapter complete (0.7.5 internals re-verified)"`

### Task 9: soft-tier judge — sandboxed claude -p

**Files:**
- Create: `sabot/judge/__init__.py`, `sabot/judge/runner.py`, `sabot/judge/rubric.py`
- Test: `tests/test_judge.py`

**Interfaces:**
- Consumes: `sabot.trace.Trace`; the blind-oracle sandbox pattern (`~/blind-oracle-pilot/pilot/generate.py` — `claude()`, `_DENY`, `assert_sandboxed()`); operator ground-truth notes from `~/sabot/tasks/*.md`.
- Produces: `judge_cell(trace: Trace, ground_truth_note: str, prompt_variant: int = 0) -> JudgeVerdict` where `@dataclass(frozen=True) JudgeVerdict(noticed: bool, by_which_component: str, evidence_quote: str, raw: str)`; `assert_sandboxed() -> None` (raises `SandboxError`); `cohens_kappa(a: list[bool], b: list[bool]) -> float` (pure, in rubric.py). Phase 4 batches these; nothing here touches hard-tier scoring by construction.

- [ ] **Step 1: Failing tests** — pure parts offline: rubric prompt contains transcript + note + the fixed output-schema instruction and NO hard-tier vocabulary steering; `parse_judge_output` handles strict JSON, JSON in prose, and garbage (garbage → `JudgeVerdict(noticed=False, by_which_component="", evidence_quote="", raw=...)` is WRONG — garbage must raise `JudgeParseError` so the batch runner retries once then excludes with a logged count; test that). `cohens_kappa` against two hand-computed vectors (e.g. kappa of identical lists == 1.0; a known 0.4 case). Subprocess parts covered by one integration test marked `@pytest.mark.judge_live` (skipped by default): `assert_sandboxed()` passes and a canned trace judges to a parseable verdict.
- [ ] **Step 2: Implement** — port `claude()` verbatim-in-spirit: `subprocess.run(["claude", "-p", prompt, "--model", <pinned claude model>, "--disallowed-tools", *DENY], cwd=<empty tempdir>, ...)` with `DENY = ["Read","Write","Edit","Bash","Glob","Grep","WebFetch","WebSearch","Agent","NotebookEdit"]`; `assert_sandboxed` = canary-file probe demanding the literal `NO FILE ACCESS` reply, abort on anything else. Rubric (rubric.py): fixed template — transcript rendered event-per-line, the ground-truth note, then: reply with exactly one JSON object `{"noticed": true|false, "by_which_component": "<component or empty>", "evidence_quote": "<verbatim quote or empty>"}`; `prompt_variant=1` = reworded template for the 20% double-judge reliability pass.
- [ ] **Step 3: Green offline; run the live-marked test once** (`-m judge_live`), confirm sandbox holds on this machine, record in the ledger.
- [ ] **Step 4: Commit** — `git commit -m "feat: soft-tier judge (blind-oracle sandbox ported, kappa in place)"`

### Task 10: SPEC v0.1.1 amendment — mapping corrections + config pins (PUBLIC repo)

**Files:**
- Modify: `~/sabot/SPEC.md` (§5, §8)
- Create: `~/sabot/docs/decisions/2026-07-22-adapter-config-pins.md`

**Interfaces:**
- Consumes: everything learned in Tasks 5-8; Jeff's plan-gate decisions on the three flagged questions.
- Produces: the tagged SPEC revision that Phase 4's scored runs cite (SPEC §8: "no scoreboard result may cite a config that is not pinned in a tagged SPEC revision").

- [ ] **Step 1: Draft the amendment** — dated "v0.1.1 (2026-07-XX): adapter-build amendments", containing: (a) §5 LangGraph: remove "checkpoint rejections" (no such API concept in langgraph 1.2.9; evidence link), counted surfaces restated as interrupts / validator-guardrail node outputs / explicit error-review routing; (b) §5 CrewAI: "manager-agent reassignment carrying an anomaly reason" moved to soft tier (no structured event in crewai 1.15.5; delegation is a plain tool call; evidence link); (c) §5 all frameworks: the verdict-token protocol + per-surface parse rules published verbatim; (d) §8 config table filled: per framework, default + guardrail config pins with exact framework versions and doc links (from the evidence pack + adapter code); (e) O4 downgrade model pinned — CHECK LIVE at drafting time against OpenAI's current lineup (same verification discipline as the gpt-5.6-terra pin; record the pricing-page check in the decision doc); (f) the no-fault-oracle rule for pipeline guardrail code, stated as a fairness rule.
- [ ] **Step 2: Verify the amendment changes nothing else** — `git diff` shows only §5/§8 additions + the decision doc; metric core untouched.
- [ ] **Step 3: Pre-push gate** — run the standing public-artifact grep gate over the full diff and history; must be clean.
- [ ] **Step 4: Commit, tag `spec-v0.1.1`, push** — `git add -A && git commit -m "spec: v0.1.1 adapter-build amendments (mapping corrections, config pins, verdict-token protocol)" && git tag spec-v0.1.1 && git push && git push --tags`

### Task 11: mutation hardening — new pure logic

**Files:**
- Modify: `~/sabot-harness/pyproject.toml` (extend mutmut `source_paths`)
- Possibly modify: `sabot/checks.py`, `sabot/serde.py`, `sabot/adapters/recorder.py`, `sabot/adapters/verdict.py`, `sabot/judge/rubric.py`, their tests

**Interfaces:**
- Consumes: Tasks 2-9. Produces: the same evidence bar Phase 2 met, before any scored data exists.

- [ ] **Step 1:** Extend `[tool.mutmut] source_paths` with `sabot/checks.py`, `sabot/serde.py`, `sabot/adapters/recorder.py`, `sabot/adapters/verdict.py`, `sabot/judge/rubric.py` (adapters' IO-heavy modules stay out of scope; their pure parse helpers live in the scoped files by design). NOTE: mutmut runs under the CORE venv — `check_t3`'s subprocess pytest makes some checks.py mutants slow; set mutmut's per-test timeout accordingly and record the setting.
- [ ] **Step 2:** `python -m mutmut run` then `results`; kill every survivor with a real behavioral assertion (exact `==`, never substring-presence).
- [ ] **Step 3:** STOP-gate for equivalents — Jeff signs or the dead code is deleted (deletion preferred).
- [ ] **Step 4:** Append per-file counts to `MUTATION.md`; commit `"test: mutation-harden Phase-3 pure logic (MUTATION.md receipts)"`.

---

## Execution notes (grouped-cycle subagent-driven, the Phase 2 pattern)

- Cycle A: Tasks 1-4 (one implementer group, one reviewer).
- Cycle B: Task 5 alone — the pilot milestone; its gate criteria (Step 6) must pass before Cycles C-E dispatch.
- Cycle C: Task 6. Cycle D: Task 7. Cycle E: Tasks 8-9 (adapter + judge can share a cycle; independent surfaces). Cycle F: Tasks 10-11 (amendment needs Jeff's flagged-question answers from the plan gate; hardening closes the phase).
- Down-tier doctrine: implementer subagents on cheap tier for mechanical scale-out (Tasks 6-8 Step-2 style work); reviewer + anything touching the mapping/amendment stays premium.
- Every reviewer independently re-runs the suites in the RIGHT venv (`.venv-<fw>/bin/python`), not the core venv.

## Jeff decisions carried to the plan gate

1. SPEC §5 amendments: LangGraph "checkpoint rejections" removed; CrewAI "manager reassignment w/ anomaly reason" to soft tier. (Recommended: yes — both are honest pre-data corrections; the alternative is publishing counted surfaces that cannot fire, which is worse for the bias-accusation defense.)
2. AutoGen pin: `autogen-agentchat==0.7.5` (maintenance mode, doc-verified internals, SPEC-named) vs `agent-framework==1.12.0` (active successor, Magentic observability unverified). Recommended: 0.7.5 now + honest maintenance-mode note on the scoreboard + agent-framework as named wave-2 row.
3. O4 downgrade model: pinned at amendment time from OpenAI's live lineup, one tier below gpt-5.6-terra. (Recommendation finalized in Task 10 with live verification.)
