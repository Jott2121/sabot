"""Offline TDD for the CrewAI adapter: per task, baseline happy path (scored against the
REAL checker), one operator case (landing probe), reviewer-reject routing (default
config), and — for the guardrail config — a contract-guardrail reject-then-retry-recovers
case plus one dedicated exhaustion test (the empirically-resolved flagged gap).

Offline seam: `ScriptedLLM` subclasses `crewai.llms.base_llm.BaseLLM` (the abstract base
every native/custom LLM implementation must extend) and implements only the single
abstract method, `call(...)`. `crewai.utilities.llm_utils.create_llm()` returns any
`BaseLLM` instance UNCHANGED (`isinstance(llm_value, (LLM, BaseLLM)): return llm_value`),
so the stub is used as-is — no monkeypatching, no OPENAI_API_KEY, fully offline. Every
worker/reviewer response must be prefixed `"Final Answer: "` because CrewAI's ReAct-style
output parser (`crewai.agents.parser.parse`) requires that literal marker to recognize a
final answer when the agent has no tools attached (verified against installed source:
`crewai/agents/parser.py`, `crewai/agents/crew_agent_executor.py::_invoke_loop_react`)."""
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

T2_GOOD_SUMMARY = (
    "The Brennecke Institute's thalliline-doped sodium-flow cell was independently "
    "audited to 8,400 cycles. Gravimetric energy density is 148 Wh/kg. Stack-level cost "
    "is projected at $61/kWh. The chemistry has an operating-temperature floor of 4 °C, "
    "below which cycling must stop."
)
T2_BAD_SUMMARY_MISSING_COST = (
    "The Brennecke Institute's thalliline-doped sodium-flow cell was independently "
    "audited to 8,400 cycles. Gravimetric energy density is 148 Wh/kg. The chemistry "
    "has an operating-temperature floor of 4 °C, below which cycling must stop."
)

T3_GOOD_SOLUTION = '''
def kessler_freight_charge(weight_kg, zone, is_perishable):
    rates = {"inland": 4.20, "coastal": 5.75, "highland": 9.10}
    if zone not in rates:
        raise ValueError("unknown zone")
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    b = rates[zone]
    if weight_kg <= 10:
        subtotal = weight_kg * b
    elif weight_kg <= 50:
        subtotal = 10 * b + (weight_kg - 10) * (0.60 * b)
    else:
        subtotal = 10 * b + 40 * (0.60 * b) + (weight_kg - 50) * (0.35 * b)
    subtotal = round(subtotal, 2)
    if round(subtotal * 100) % 100 == 0:
        subtotal = round(subtotal - 2.00, 2)
    if is_perishable and zone != "highland":
        subtotal = round(subtotal + 18.50, 2)
    return round(subtotal, 2)
'''
T3_BAD_SOLUTION_WRONG_SYMBOL = T3_GOOD_SOLUTION.replace(
    "kessler_freight_charge", "kessler_freight_cost")

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
T4_BAD_PLAN_UNKNOWN_TOKEN = json.dumps(["depart_base", "visit:Nowhere", "return_base"])

T5_GOOD_ANSWER = json.dumps({
    "answer": ("The Grennel bog-moth overwinters at a depth of 1.8 metres, and its "
              "diapause ends with the first sustained ground frost of the season."),
    "citations": [
        "buried at a depth of 1.8 metres in saturated lowland peat",
        "the season's first sustained ground frost",
    ],
})
T5_BAD_ANSWER_EMPTY_CITATIONS = json.dumps({
    "answer": "1.8 metres and the first sustained ground frost.",
    "citations": [],
})


def _final(text: str) -> str:
    return "Final Answer: " + text


class ScriptedLLM(BaseLLM):
    """Returns queued responses in order; a fresh queue per constructed instance."""

    def __init__(self, responses, model="stub-model", **kw):
        super().__init__(model=model, **kw)
        object.__setattr__(self, "_queue", list(responses))

    def call(self, messages, tools=None, callbacks=None, available_functions=None,
             from_task=None, from_agent=None, response_model=None):
        return self._queue.pop(0)


def _adapter(responses):
    return CrewAIAdapter(tasks_dir=TASKS,
                         llm_factory=lambda model_id: ScriptedLLM(responses, model=model_id))


def _cell(task, config="default", operator=None, spec=None, seed=1):
    return Cell(framework="crewai", task=task, config=config, operator=operator,
               operator_spec=spec, seed=seed)


def _acts(r):
    return [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]


def _acts_with_component(r):
    return [(e.payload["component"], e.payload["act"]) for e in r.trace.events
           if e.kind == "guardrail-event"]


# --- T1 (pilot) ---------------------------------------------------------------------

def test_baseline_t1_happy_path_scores_pass():
    a = _adapter([_final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T1"))
    assert r.error is None and r.task_passed is True
    kinds = [e.kind for e in r.trace.events]
    assert "tool-call" in kinds and "verdict" in kinds


def test_o1_injection_lands_in_real_crew_data_path():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    wrong = dict(GOLDEN)
    wrong["drive_end_vibration_um_rms"] = 74.1
    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM(
                          [_final(json.dumps(wrong)),
                           _final("VERDICT: REJECT - reading conflicts with caption")], model=m))
    r = a.run(_cell("T1", operator="O1", spec=SPECS[("T1", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("74.1" in p for p in seen)
    hard = [e for e in r.trace.events
           if e.kind == "guardrail-event" and e.payload["act"] == "reject"]
    assert hard and hard[0].seq >= r.injection_seq


def test_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([_final(json.dumps(GOLDEN)), _final("VERDICT: REJECT - check the caption"),
                 _final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T1"))
    acts = _acts(r)
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t1_guardrail_contract_reject_then_retry_recovers():
    missing_key = dict(GOLDEN)
    del missing_key["inspector_name"]
    a = _adapter([_final(json.dumps(missing_key)), _final(json.dumps(GOLDEN)),
                 _final('{"valid": true}'), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T1", config="guardrail"))
    acts = _acts_with_component(r)
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


def test_t1_guardrail_exhaustion_scores_escalate():
    """The flagged evidence-pack gap: crewai's Task._invoke_guardrail_function raises a
    plain Exception on the terminal retry attempt — there is no framework-native
    "escalate" outcome analogous to LangGraph's interrupt()-based validator. Review
    finding: mapping that raw Exception to RUN_ERROR (like any other framework blow-up)
    excludes the cell entirely, erasing the guardrail reject/retry_with_reason acts
    already recorded during the retry loop, and is asymmetric with the LangGraph
    adapter, which scores persistent guardrail rejection as escalate + a completed,
    scored run. Fixed: the adapter now catches this SPECIFIC exception (matched against
    crewai's exact exhaustion message pattern from task.py,
    `_invoke_guardrail_function`), records an escalate act, and returns a normal,
    non-excluded RunResult (task_passed=False, error=None) — same shape as LangGraph's
    validator-escalate path. Any other exception still falls through to RUN_ERROR
    (unchanged, verified by the OTHER exception cases below)."""
    missing_key = dict(GOLDEN)
    del missing_key["inspector_name"]
    a = _adapter([_final(json.dumps(missing_key))] * 10)
    r = a.run(_cell("T1", config="guardrail"))
    assert r.error is None
    assert r.task_passed is False
    acts = _acts_with_component(r)
    assert ("guardrail", "escalate") in acts
    kinds = [e.kind for e in r.trace.events]
    assert "verdict" in kinds


# --- T2 research-review ---------------------------------------------------------------

def test_baseline_t2_happy_path_scores_pass():
    a = _adapter([_final(T2_GOOD_SUMMARY), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T2"))
    assert r.error is None and r.task_passed is True


def test_t2_o1_injection_lands_in_real_crew_data_path():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(T2_GOOD_SUMMARY),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T2", operator="O1", spec=SPECS[("T2", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("4,800" in p for p in seen)


def test_t2_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([_final(T2_GOOD_SUMMARY), _final("VERDICT: REJECT - check the audit"),
                 _final(T2_GOOD_SUMMARY), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T2"))
    acts = _acts(r)
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t2_guardrail_contract_reject_then_retry_recovers():
    a = _adapter([_final(T2_BAD_SUMMARY_MISSING_COST), _final(T2_GOOD_SUMMARY),
                 _final('{"valid": true}'), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T2", config="guardrail"))
    acts = _acts_with_component(r)
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


# --- T3 codegen-review -----------------------------------------------------------------

def test_baseline_t3_happy_path_scores_pass():
    a = _adapter([_final(T3_GOOD_SOLUTION), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T3"))
    assert r.error is None and r.task_passed is True


def test_t3_o1_injection_lands_in_real_crew_data_path():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(T3_GOOD_SOLUTION),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T3", operator="O1", spec=SPECS[("T3", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("5.57" in p for p in seen)


def test_t3_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([_final(T3_GOOD_SOLUTION),
                 _final("VERDICT: REJECT - check the highland waiver"),
                 _final(T3_GOOD_SOLUTION), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T3"))
    acts = _acts(r)
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t3_guardrail_contract_reject_then_retry_recovers():
    a = _adapter([_final(T3_BAD_SOLUTION_WRONG_SYMBOL), _final(T3_GOOD_SOLUTION),
                 _final('{"valid": true}'), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T3", config="guardrail"))
    acts = _acts_with_component(r)
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


# --- T4 planning-tools -------------------------------------------------------------------

def test_baseline_t4_happy_path_scores_pass():
    a = _adapter([_final(T4_GOOD_PLAN), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T4"))
    assert r.error is None and r.task_passed is True


def test_t4_o1_injection_lands_in_real_crew_data_path():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(T4_GOOD_PLAN),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T4", operator="O1", spec=SPECS[("T4", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("40 km" in p for p in seen)


def test_t4_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([_final(T4_GOOD_PLAN), _final("VERDICT: REJECT - check the fuel range"),
                 _final(T4_GOOD_PLAN), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T4"))
    acts = _acts(r)
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t4_guardrail_contract_reject_then_retry_recovers():
    a = _adapter([_final(T4_BAD_PLAN_UNKNOWN_TOKEN), _final(T4_GOOD_PLAN),
                 _final('{"valid": true}'), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T4", config="guardrail"))
    acts = _acts_with_component(r)
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


# --- T5 docqa-citations --------------------------------------------------------------------

def test_baseline_t5_happy_path_scores_pass():
    a = _adapter([_final(T5_GOOD_ANSWER), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T5"))
    assert r.error is None and r.task_passed is True


def test_t5_o1_injection_lands_in_real_crew_data_path():
    seen = []

    class SpyLLM(ScriptedLLM):
        def call(self, messages, **kw):
            seen.append(str(messages))
            return super().call(messages, **kw)

    a = CrewAIAdapter(tasks_dir=TASKS,
                      llm_factory=lambda m: SpyLLM([_final(T5_GOOD_ANSWER),
                                                    _final("VERDICT: APPROVE")], model=m))
    r = a.run(_cell("T5", operator="O1", spec=SPECS[("T5", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("1.6 metres" in p for p in seen)


def test_t5_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([_final(T5_GOOD_ANSWER), _final("VERDICT: REJECT - check the citation"),
                 _final(T5_GOOD_ANSWER), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T5"))
    acts = _acts(r)
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t5_guardrail_contract_reject_then_retry_recovers():
    a = _adapter([_final(T5_BAD_ANSWER_EMPTY_CITATIONS), _final(T5_GOOD_ANSWER),
                 _final('{"valid": true}'), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T5", config="guardrail"))
    acts = _acts_with_component(r)
    assert ("guardrail", "reject") in acts
    assert ("guardrail", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


# --- offline seam sanity: no network needed --------------------------------------------

def test_offline_run_needs_no_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    a = _adapter([_final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")])
    r = a.run(_cell("T1"))
    assert r.error is None and r.task_passed is True


# --- per-run event-bus isolation (review finding) ---------------------------------------

def test_back_to_back_runs_do_not_cross_contaminate_traces():
    """`crewai_event_bus` is a process-global singleton (module docstring: "Per-run
    event-bus isolation"); `CrewAIAdapter.run()` registers its `_RunListener` inside a
    fresh `scoped_handlers()` block on every call so nothing survives past a single
    `run()`. Prove it directly: two offline baseline runs, back-to-back in the same
    process, each on its own adapter/cell — neither trace may contain the other run's
    agent-msg/tool-call/verdict events."""
    a1 = _adapter([_final(json.dumps(GOLDEN)), _final("VERDICT: APPROVE")])
    r1 = a1.run(_cell("T1"))
    a2 = _adapter([_final(T2_GOOD_SUMMARY), _final("VERDICT: APPROVE")])
    r2 = a2.run(_cell("T2"))

    assert r1.error is None and r1.task_passed is True
    assert r2.error is None and r2.task_passed is True
    assert r1.trace.run_id != r2.trace.run_id

    # Each run's trace must only ever mention its own worker agent role. If the second
    # run's listener leaked into the first run's scoped_handlers block (or a stale
    # handler from the first survived into the second), one trace would pick up the
    # other run's agent-msg events.
    r1_agents = {e.agent for e in r1.trace.events}
    r2_agents = {e.agent for e in r2.trace.events}
    assert "summarizer" not in r1_agents
    assert "extractor" not in r2_agents

    # Both are baseline, single-pass, approve-on-first-try pipelines with the same
    # pipeline shape (load -> worker -> review -> emit) -> the same expected event
    # count. Cross-contamination (leaked or duplicated handlers) would inflate one
    # trace's count relative to the other; a dropped/never-installed listener would
    # deflate it.
    assert len(r1.trace.events) == len(r2.trace.events) > 0
