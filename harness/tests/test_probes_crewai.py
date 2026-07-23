"""Injection-landing probes: one per operator (O1-O6), each proving the fault reaches a
real data path inside an actual CrewAI `Crew.kickoff()` run (not merely that `apply()`
mutates a dict in isolation — sabot/operators.py already covers that in
tests/test_operators_*.py). Pattern from Task 5/7's
`test_o1_injection_lands_in_real_*_data_path`: a SpyLLM captures what the real framework
did with the corrupted value.

All probes use T1 (the reviewed pilot pipeline) for a consistent, minimal harness; the
same seams are wired identically in T2-T5 (see tests/test_crewai_adapter.py for the
per-task coverage)."""
import json
import pathlib

import pytest
pytest.importorskip("crewai")  # this venv may be .venv-langgraph/.venv-autogen
from crewai.llms.base_llm import BaseLLM

from sabot.adapters.crewai_adapter import CrewAIAdapter
from sabot.adapters.operator_specs import SPECS, DOWNGRADE_MODEL
from sabot.runner import Cell

TASKS = pathlib.Path.home() / "sabot" / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())


def _final(text: str) -> str:
    return "Final Answer: " + text


class ScriptedLLM(BaseLLM):
    def __init__(self, responses, model="stub-model", **kw):
        super().__init__(model=model, **kw)
        object.__setattr__(self, "_queue", list(responses))

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        return self._queue.pop(0)


def _cell(operator, seed=1, config="default"):
    return Cell(framework="crewai", task="T1", config=config, operator=operator,
               operator_spec=SPECS[("T1", operator)], seed=seed)


def test_o1_tool_lie_lands_in_extractor_prompt():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(json.dumps(GOLDEN)),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("O1"))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any(SPECS[("T1", "O1")]["replace"] in p for p in seen)


def test_o2_false_success_lands_in_reviewer_prompt():
    # The reviewer's own deterministic pre-check artifact is replaced by the canned
    # "fake success" string BEFORE the reviewer LLM ever sees it — prove the fake text
    # actually reaches the reviewer's prompt input (the real data path), not just that
    # sabot.operators.apply() can produce it in isolation.
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(json.dumps(GOLDEN)),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("O2"))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any(SPECS[("T1", "O2")]["fake_report"] in p for p in seen)


def test_o3_message_alteration_lands_in_reviewer_prompt():
    # The extractor's real output contains the GOLDEN unit_id; the handoff to the
    # reviewer must carry the swapped id, not the real one.
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(json.dumps(GOLDEN)),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("O3"))
    assert r.injection_verified is True and r.injection_seq is not None
    spec = SPECS[("T1", "O3")]
    assert any(spec["replace"] in p for p in seen)
    # the reviewer's own prompt (2nd call) is the one that must carry the corruption
    assert spec["replace"] in seen[-1]


def test_o4_model_downgrade_lands_in_the_built_worker_client():
    built = []

    def factory(model_id):
        m = ScriptedLLM([_final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")],
                       model=model_id)
        built.append(m)
        return m

    a = CrewAIAdapter(tasks_dir=TASKS, llm_factory=factory)
    r = a.run(_cell("O4"))
    assert r.injection_verified is True and r.injection_seq is not None
    # the landing probe IS this assertion: the built client's `.model` equals the override,
    # proving the config mutation actually reached model construction, not just the spec dict
    assert any(m.model == DOWNGRADE_MODEL for m in built)
    assert any(m.model == "gpt-5.6-terra" for m in built)   # reviewer stays on-tier


def test_o5_stale_context_lands_in_extractor_prompt():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(json.dumps(GOLDEN)),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("O5"))
    assert r.injection_verified is True and r.injection_seq is not None
    stale = SPECS[("T1", "O5")]["stale_content"]
    assert any(stale in p for p in seen)
    # lands in the FIRST (extractor) call, before the reviewer ever runs
    assert stale in seen[0]


def test_o6_silent_noop_suppresses_write_and_reports_done():
    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: ScriptedLLM([_final(json.dumps(GOLDEN)),
                                                         _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("O6"))
    assert r.injection_verified is True and r.injection_seq is not None
    # the write tool's side effect was suppressed: no real artifact -> check() fails
    assert r.task_passed is False
    # ... yet the pipeline was told "done": the write tool's reported message is in-trace
    reported = [e for e in r.trace.events if e.kind == "agent-msg"
               and "write_output reported:" in e.payload["text"]]
    assert reported
    assert SPECS[("T1", "O6")]["success_response"] in reported[0].payload["text"]
