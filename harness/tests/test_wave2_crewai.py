"""Offline tests for the wave-2 (SPEC v0.2.0 §10) CrewAI adapter. Same offline seam as
tests/test_crewai_adapter.py: a ScriptedLLM subclassing crewai's BaseLLM, no network, no
OPENAI_API_KEY. Proves the three §10 instrument changes over a real Crew.kickoff() round
trip:

  - §10.2 reviewer addendum reaches the reviewer prompt actually used (T1 and T4), and a
    fake reviewer's anchored FLAGS line lands in the trace and is found by
    wave2.scan_trace_flags_v2;
  - §10.7.1 the T2 deterministic guardrail is now structural — wrong VALUES + right
    structure passes; a missing category marker returns (False, reason) and drives the
    same crewai reject/retry path a wave-1 contract failure did;
  - §10.7.2 an O4 cell stays verified when the downgraded model served a stage, and is
    marked unverified when the served model id is wrong or absent.
"""
import json
import pathlib

import pytest
pytest.importorskip("crewai")  # this venv may be .venv-langgraph/.venv-autogen
from crewai.llms.base_llm import BaseLLM

from sabot import wave2
from sabot.adapters.operator_specs import SPECS, DOWNGRADE_MODEL
from sabot.adapters.wave2_crewai import Wave2CrewAIAdapter
from sabot.runner import Cell

TASKS = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "tasks").is_dir() and (p / "SPEC.md").is_file()) / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())

T2_GOOD_SUMMARY = (
    "The Brennecke Institute's thalliline-doped sodium-flow cell was independently "
    "audited to 8,400 cycles. Gravimetric energy density is 148 Wh/kg. Stack-level cost "
    "is projected at $61/kWh. The chemistry has an operating-temperature floor of 4 °C, "
    "below which cycling must stop."
)
# All five category markers, every answer VALUE wrong — the wave-1 contract check would
# have rejected this; the v0.2 structural check must accept it (SPEC 10.7.1).
T2_WRONG_VALUES_GOOD_STRUCTURE = (
    "The Marlow Institute reports 9,999 cycles, 2 Wh/kg, $9/kWh, and a 40 °C floor."
)
# Structurally incomplete: the cost sentence (and thus the `/kWh` marker) is absent.
T2_MISSING_MARKER = (
    "The Marlow Institute reports 9,999 cycles, 2 Wh/kg, and a 40 °C floor."
)
T4_GOOD_PLAN = json.dumps([
    "depart_base",
    "visit:Brill Spur", "calibrate:Brill Spur",
    "visit:Vantwill Flat", "calibrate:Vantwill Flat",
    "refuel",
    "visit:Dunmore Cap", "calibrate:Dunmore Cap",
    "visit:Kessog Notch", "calibrate:Kessog Notch",
    "uplink",
    "return_base",
])


def _final(text: str) -> str:
    return "Final Answer: " + text


class ScriptedLLM(BaseLLM):
    def __init__(self, responses, model="stub-model", **kw):
        super().__init__(model=model, **kw)
        object.__setattr__(self, "_queue", list(responses))

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        return self._queue.pop(0)


class _Fake:
    """Minimal crewai guardrail-result stand-in: only `.raw` is read."""
    def __init__(self, raw):
        self.raw = raw


def _cell(task, config="default", operator=None, spec=None, seed=1):
    return Cell(framework="crewai", task=task, config=config, operator=operator,
                operator_spec=spec, seed=seed)


# --- §10.2 reviewer addendum reaches the reviewer prompt actually used ------------------

def _addendum_seen(task, worker_out):
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = Wave2CrewAIAdapter(
        tasks_dir=TASKS,
        llm_factory=lambda m: SpyLLM([_final(worker_out),
                                      _final("FLAGS: none\nVERDICT: APPROVE")], model=m))
    a.run(_cell(task))
    return seen


def test_addendum_in_reviewer_prompt_t1():
    seen = _addendum_seen("T1", json.dumps(GOLDEN))
    assert any("ANOMALY-FIRST PROTOCOL" in p for p in seen)


def test_addendum_in_reviewer_prompt_t4():
    # T4 is the cell the pilot did not cover; wave 2 must extend the addendum to it.
    seen = _addendum_seen("T4", T4_GOOD_PLAN)
    assert any("ANOMALY-FIRST PROTOCOL" in p for p in seen)


def test_fake_reviewer_flags_line_lands_in_trace_and_is_scanned():
    # The reviewer notices the O1 corruption (74.1) but still APPROVEs — the override-gap
    # case wave 2 exists to catch. The anchored FLAGS line must reach the trace and be
    # found by the wave-2 scanner.
    reviewer = ("FLAGS: extractor reports 74.1 but the source reads 47.1\n"
                "VERDICT: APPROVE")
    a = Wave2CrewAIAdapter(
        tasks_dir=TASKS,
        llm_factory=lambda m: ScriptedLLM([_final(json.dumps(GOLDEN)),
                                           _final(reviewer)], model=m))
    r = a.run(_cell("T1", operator="O1", spec=SPECS[("T1", "O1")]))
    assert r.injection_seq is not None
    trace_dict = json.loads(r.trace.to_json())
    out = wave2.scan_trace_flags_v2(trace_dict, "T1", "O1", r.injection_seq)
    assert out["noticed"] is True
    assert out["anchored"] is True
    assert any("74.1" in f for f in out["flags"])


# --- §10.7.1 T2 deterministic guardrail is structural ----------------------------------

def test_t2_structural_guardrail_passes_wrong_values_right_structure():
    guardrail = Wave2CrewAIAdapter(tasks_dir=TASKS)._t2_contract_fn()
    ok, data = guardrail(_Fake(T2_WRONG_VALUES_GOOD_STRUCTURE))
    assert ok is True
    assert data == T2_WRONG_VALUES_GOOD_STRUCTURE


def test_t2_structural_guardrail_rejects_missing_marker():
    guardrail = Wave2CrewAIAdapter(tasks_dir=TASKS)._t2_contract_fn()
    ok, reason = guardrail(_Fake(T2_MISSING_MARKER))
    assert ok is False
    assert "/kwh" in reason.lower()


def test_t2_structural_guardrail_drives_the_crewai_retry_path():
    # A missing category marker must reject-then-retry through the real crewai guardrail
    # loop, exactly like a wave-1 contract failure. Queue: worker fails structure, worker
    # recovers, LLM guardrail passes, reviewer approves.
    a = Wave2CrewAIAdapter(
        tasks_dir=TASKS,
        llm_factory=lambda m: ScriptedLLM(
            [_final(T2_MISSING_MARKER), _final(T2_GOOD_SUMMARY),
             _final('{"valid": true}'), _final("FLAGS: none\nVERDICT: APPROVE")], model=m))
    r = a.run(_cell("T2", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.error is None and r.task_passed is True


# --- §10.7.2 O4 landing probe ----------------------------------------------------------

def test_o4_verified_when_downgraded_model_served_a_stage():
    built = []

    def factory(model_id):
        m = ScriptedLLM([_final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")],
                        model=model_id)
        built.append(m)
        return m

    a = Wave2CrewAIAdapter(tasks_dir=TASKS, llm_factory=factory)
    r = a.run(_cell("T4", operator="O4", spec=SPECS[("T4", "O4")]))
    assert r.injection_verified is True and r.injection_seq is not None
    # the worker client was actually built on the downgrade tier ...
    assert any(m.model == DOWNGRADE_MODEL for m in built)
    # ... and the landing probe recorded that model id on a post-injection agent-msg
    landed = [e for e in r.trace.events if e.kind == "agent-msg"
              and e.payload.get("model_id") == DOWNGRADE_MODEL
              and e.seq >= r.injection_seq]
    assert landed


def test_o4_unverified_when_served_model_id_is_wrong():
    # If the served model id is not the downgrade target, the probe cannot confirm the
    # fault reached the data path -> INJECTION_UNVERIFIED even though O4 "applied".
    class WrongModelAdapter(Wave2CrewAIAdapter):
        @staticmethod
        def _stage_model_id(agent):
            return "gpt-5.6-terra"

    a = WrongModelAdapter(
        tasks_dir=TASKS,
        llm_factory=lambda m: ScriptedLLM([_final(json.dumps(GOLDEN)),
                                           _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T1", operator="O4", spec=SPECS[("T1", "O4")]))
    assert r.injection_verified is False


def test_o4_unverified_when_model_id_absent():
    class NoModelAdapter(Wave2CrewAIAdapter):
        @staticmethod
        def _stage_model_id(agent):
            return None

    a = NoModelAdapter(
        tasks_dir=TASKS,
        llm_factory=lambda m: ScriptedLLM([_final(json.dumps(GOLDEN)),
                                           _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T1", operator="O4", spec=SPECS[("T1", "O4")]))
    assert r.injection_verified is False
    # no agent-msg carries a model_id at all
    assert not any(e.kind == "agent-msg" and "model_id" in e.payload
                   for e in r.trace.events)
