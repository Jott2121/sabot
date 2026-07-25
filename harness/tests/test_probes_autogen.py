"""Injection-landing probes: one per operator (O1-O6), each proving the fault reaches a
real data path inside an actual AutoGen `Team.run_stream()`/`AssistantAgent` round trip
(not merely that `apply()` mutates a dict in isolation — `sabot/operators.py` already
covers that in `tests/test_operators_*.py`). Pattern from Task 5/7's
`test_o1_injection_lands_in_real_*_data_path`: a spy client captures what the real
framework did with the corrupted value.

All probes use T1/default config for a consistent, minimal harness EXCEPT O3, which is
also probed in guardrail config (its landing point differs by config — see the adapter
module docstring's "Guardrail config... operator landing points" section)."""
import json
import pathlib

import pytest
pytest.importorskip("autogen_agentchat")  # this venv may be .venv-langgraph/.venv-crewai
from autogen_ext.models.replay import ReplayChatCompletionClient

from sabot.adapters.autogen_adapter import AutoGenAdapter
from sabot.adapters.operator_specs import SPECS, DOWNGRADE_MODEL
from sabot.runner import Cell

TASKS = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "tasks").is_dir() and (p / "SPEC.md").is_file()) / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())


def _cell(operator, seed=1, config="default", spec_task="T1"):
    return Cell(framework="autogen", task="T1", config=config, operator=operator,
               operator_spec=SPECS[(spec_task, operator)], seed=seed)


def _spy_shared_factory(responses, seen):
    class SpyReplay(ReplayChatCompletionClient):
        async def create(self, messages, **kw):
            seen.append(str(messages))
            return await super().create(messages, **kw)

    def factory(model_id):
        return SpyReplay(list(responses))
    return factory


def _ledger(satisfied, progress, in_loop, instr, next_speaker):
    return json.dumps({
        "is_request_satisfied": {"reason": "r", "answer": satisfied},
        "is_progress_being_made": {"reason": "r", "answer": progress},
        "is_in_loop": {"reason": "r", "answer": in_loop},
        "instruction_or_question": {"reason": "r", "answer": instr},
        "next_speaker": {"reason": "r", "answer": next_speaker},
    })


def test_o1_tool_lie_lands_in_extractor_prompt():
    seen = []
    a = AutoGenAdapter(tasks_dir=TASKS,
                       client_factory=_spy_shared_factory(
                           [json.dumps(GOLDEN), "VERDICT: APPROVE"], seen))
    r = a.run(_cell("O1"))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any(SPECS[("T1", "O1")]["replace"] in p for p in seen)


def test_o2_false_success_lands_in_critic_prompt():
    # The critic's own deterministic pre-check artifact is replaced by the canned "fake
    # success" string BEFORE the critic's task text is built — prove the fake text actually
    # reaches the critic's real task input (the framework data path), not just that
    # sabot.operators.apply() can produce it in isolation.
    seen = []
    a = AutoGenAdapter(tasks_dir=TASKS,
                       client_factory=_spy_shared_factory(
                           [json.dumps(GOLDEN), "VERDICT: APPROVE"], seen))
    r = a.run(_cell("O2"))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any(SPECS[("T1", "O2")]["fake_report"] in p for p in seen)


def test_o3_message_alteration_lands_in_critic_prompt_default_config():
    seen = []
    a = AutoGenAdapter(tasks_dir=TASKS,
                       client_factory=_spy_shared_factory(
                           [json.dumps(GOLDEN), "VERDICT: APPROVE"], seen))
    r = a.run(_cell("O3"))
    assert r.injection_verified is True and r.injection_seq is not None
    spec = SPECS[("T1", "O3")]
    assert any(spec["replace"] in p for p in seen)
    # the critic's own task text (2nd real model call) is the one that must carry it
    assert spec["replace"] in seen[-1]


def test_o3_message_alteration_lands_in_guardrail_config():
    # MagenticOneGroupChat has no worker->critic handoff (no critic at all) — O3 lands on
    # the worker's captured final text before it becomes the checked artifact (see adapter
    # module docstring). Prove it lands by proving the checked artifact fails check() on
    # the corrupted unit_id even though the worker's REAL output was the correct golden.
    orch_responses = ["facts text", "plan text",
                      _ledger(False, True, False, "go", "extractor"),
                      _ledger(True, True, False, "done", "extractor"), "final answer text"]
    calls = {"n": 0}

    def factory(model_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return ReplayChatCompletionClient([json.dumps(GOLDEN)])
        return ReplayChatCompletionClient(list(orch_responses))

    a = AutoGenAdapter(tasks_dir=TASKS, client_factory=factory)
    r = a.run(_cell("O3", config="guardrail"))
    assert r.injection_verified is True and r.injection_seq is not None
    assert r.task_passed is False    # the swapped unit_id fails the exact-match checker


def test_o4_model_downgrade_lands_in_the_built_worker_client():
    built = []

    def factory(model_id):
        built.append(model_id)
        return ReplayChatCompletionClient([json.dumps(GOLDEN), "VERDICT: APPROVE"])

    a = AutoGenAdapter(tasks_dir=TASKS, client_factory=factory)
    r = a.run(_cell("O4"))
    assert r.injection_verified is True and r.injection_seq is not None
    # the landing probe IS this assertion: `client_factory` was actually called with the
    # override model id, proving the config mutation reached model construction
    assert DOWNGRADE_MODEL in built
    assert "gpt-5.6-terra" in built   # critic stays on-tier


def test_o5_stale_context_lands_in_extractor_prompt():
    seen = []
    a = AutoGenAdapter(tasks_dir=TASKS,
                       client_factory=_spy_shared_factory(
                           [json.dumps(GOLDEN), "VERDICT: APPROVE"], seen))
    r = a.run(_cell("O5"))
    assert r.injection_verified is True and r.injection_seq is not None
    stale = SPECS[("T1", "O5")]["stale_content"]
    assert any(stale in p for p in seen)
    # lands in the FIRST (extractor) call, before the critic ever runs
    assert stale in seen[0]


def test_o6_silent_noop_suppresses_write_and_reports_done():
    a = AutoGenAdapter(tasks_dir=TASKS,
                       client_factory=lambda m: ReplayChatCompletionClient(
                           [json.dumps(GOLDEN), "VERDICT: APPROVE"]))
    r = a.run(_cell("O6"))
    assert r.injection_verified is True and r.injection_seq is not None
    # the write tool's side effect was suppressed: no real artifact -> check() fails
    assert r.task_passed is False
    # ... yet the pipeline was told "done": the write tool's reported message is in-trace
    reported = [e for e in r.trace.events if e.kind == "agent-msg"
               and "write_output reported:" in e.payload["text"]]
    assert reported
    assert SPECS[("T1", "O6")]["success_response"] in reported[0].payload["text"]
