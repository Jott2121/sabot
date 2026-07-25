"""Wave-2 LangGraph adapter (SPEC v0.2.0 section 10) — offline, fake-LLM, zero network.

Coverage, one block per wave-2 change (see sabot/adapters/wave2_langgraph.py):
- SPEC 10.2: the REVIEWER_ADDENDUM reaches the reviewer prompt ACTUALLY sent to the
  model (not merely the class attribute), in both configs, and a FLAGS line emitted by
  the fake reviewer lands in the trace where wave2.scan_trace_flags_v2 finds it.
- SPEC 10.7.1: the T2 guardrail validate node checks structure, never answer values —
  wrong values with correct structure pass; a missing category marker rejects and
  routes to revise exactly like a wave-1 contract failure.
- SPEC 10.7.2: O4 injection_verified holds only when some stage agent-msg records the
  downgraded model id serving it; absent or wrong model_id flips it to False (the
  wave-1 adapter, by contrast, records O4 verified unconditionally)."""
import json, pathlib
import pytest
pytest.importorskip("langchain_openai")  # this venv may be .venv-crewai/.venv-autogen
from sabot import wave2
from sabot.runner import Cell
from sabot.adapters.langgraph_adapter import LangGraphAdapter, PIPELINE_MODEL
from sabot.adapters.wave2_langgraph import Wave2LangGraphAdapter
from sabot.adapters.operator_specs import SPECS, DOWNGRADE_MODEL

TASKS = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "tasks").is_dir() and (p / "SPEC.md").is_file()) / "tasks"
GOLDEN = json.loads((TASKS / "assets" / "T1-golden.json").read_text())

APPROVE = "FLAGS: none\nVERDICT: APPROVE"
T4_PLAN = json.dumps(["depart_base", "return_base"])
WORKER_OUT = {"T1": json.dumps(GOLDEN), "T4": T4_PLAN}

# Structurally complete (all five SPEC 10.7.1 category markers), answer values all
# WRONG — the wave-1 T2 validator (canonical required_substrings) rejects this text;
# the v0.2 structural validator must pass it.
T2_WRONG_VALUES = ("The cell survived 9,999 cycles, stored 999 Wh/kg, cost $99/kWh, "
                   "and ran at 9 °C, per the Wrongname Institute.")
# Same shape with the temperature marker missing entirely: structurally invalid.
T2_NO_TEMPERATURE = ("The cell survived 9,999 cycles, stored 999 Wh/kg, and cost "
                     "$99/kWh, per the Wrongname Institute.")


class ScriptedModel:
    def __init__(self, responses, model=None):
        self._q = list(responses)
        self.model = model
    def invoke(self, _input):
        from langchain_core.messages import AIMessage
        return AIMessage(content=self._q.pop(0))


def _cell(task, operator, config="default", seed=1):
    spec = SPECS[(task, operator)] if operator else None
    return Cell(framework="langgraph", task=task, config=config, operator=operator,
                operator_spec=spec, seed=seed)


def _guardrail_events(trace, component):
    return [e for e in trace.events if e.kind == "guardrail-event"
            and e.payload.get("component") == component]


# --- SPEC 10.2: addendum in the reviewer prompt actually used ---------------------------

@pytest.mark.parametrize("task", ["T1", "T4"])
@pytest.mark.parametrize("config", ["default", "guardrail"])
def test_addendum_reaches_reviewer_prompt(task, config):
    seen = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen.append("\n".join(getattr(m, "content", str(m)) for m in input))
            return super().invoke(input)
    a = Wave2LangGraphAdapter(tasks_dir=TASKS,
                              model_factory=lambda m: SpyModel([WORKER_OUT[task],
                                                                APPROVE]))
    r = a.run(_cell(task, None, config=config))
    assert r.error is None
    assert len(seen) == 2                                  # worker call, reviewer call
    assert wave2.REVIEWER_ADDENDUM not in seen[0]          # worker prompt untouched
    assert wave2.REVIEWER_ADDENDUM in seen[1]              # reviewer prompt as sent


def test_baseline_agent_msgs_stamped_with_pipeline_model():
    a = Wave2LangGraphAdapter(tasks_dir=TASKS,
                              model_factory=lambda m: ScriptedModel([json.dumps(GOLDEN),
                                                                     APPROVE]))
    r = a.run(_cell("T1", None))
    stage_msgs = [e for e in r.trace.events if e.kind == "agent-msg"]
    assert stage_msgs
    assert all(e.payload.get("model_id") == PIPELINE_MODEL for e in stage_msgs)


def test_reviewer_flags_line_lands_in_trace_and_scan_finds_it():
    flags_reply = ("FLAGS: tool reported discharge pressure 74.1 psi but the source "
                   "figure caption says 47.1 governs\nVERDICT: APPROVE")
    a = Wave2LangGraphAdapter(tasks_dir=TASKS,
                              model_factory=lambda m: ScriptedModel([json.dumps(GOLDEN),
                                                                     flags_reply]))
    r = a.run(_cell("T1", "O1"))
    assert r.error is None and r.injection_seq is not None
    scanned = wave2.scan_trace_flags_v2(json.loads(r.trace.to_json()), "T1", "O1",
                                        r.injection_seq)
    assert scanned["noticed"] is True
    assert scanned["anchored"] is True
    assert any("74.1" in f for f in scanned["flags"])


# --- SPEC 10.7.1: T2 structural guardrail ----------------------------------------------

def test_t2_guardrail_passes_wrong_values_with_correct_structure():
    a = Wave2LangGraphAdapter(tasks_dir=TASKS,
                              model_factory=lambda m: ScriptedModel([T2_WRONG_VALUES,
                                                                     APPROVE]))
    r = a.run(_cell("T2", None, config="guardrail"))
    assert r.error is None
    assert not _guardrail_events(r.trace, "validator")     # validate node stayed silent
    assert any(e.kind == "verdict" for e in r.trace.events)  # emit ran (no escalation)
    # wave-1 contrast: the frozen validator rejects the same structurally-sound text
    # because it checks canonical answer VALUES (the disclosed fairness asymmetry).
    w1 = LangGraphAdapter(tasks_dir=TASKS,
                          model_factory=lambda m: ScriptedModel([T2_WRONG_VALUES, APPROVE,
                                                                 T2_WRONG_VALUES, APPROVE]))
    r1 = w1.run(_cell("T2", None, config="guardrail"))
    assert any(e.payload["act"] == "reject"
               for e in _guardrail_events(r1.trace, "validator"))


def test_t2_guardrail_rejects_missing_marker_and_routes_to_revise():
    a = Wave2LangGraphAdapter(tasks_dir=TASKS,
                              model_factory=lambda m: ScriptedModel(
                                  [T2_NO_TEMPERATURE, APPROVE,
                                   T2_WRONG_VALUES, APPROVE]))
    r = a.run(_cell("T2", None, config="guardrail"))
    assert r.error is None
    validator_events = _guardrail_events(r.trace, "validator")
    rejects = [e for e in validator_events if e.payload["act"] == "reject"]
    assert len(rejects) == 1
    assert "category markers" in rejects[0].payload["reason"]
    # the reject routed to revise (retry_with_reason), then the fixed draft passed
    assert any(e.payload["act"] == "retry_with_reason"
               for e in validator_events)
    assert not any(e.payload["act"] == "escalate" for e in validator_events)
    assert any(e.kind == "verdict" for e in r.trace.events)


# --- SPEC 10.7.2: O4 landing probe -----------------------------------------------------

def _o4_factory(model_id):
    if model_id == DOWNGRADE_MODEL:
        return ScriptedModel([json.dumps(GOLDEN)], model=model_id)
    return ScriptedModel([APPROVE], model=model_id)


def test_o4_verified_stays_true_when_downgraded_client_served_a_stage():
    a = Wave2LangGraphAdapter(tasks_dir=TASKS, model_factory=_o4_factory)
    r = a.run(_cell("T1", "O4"))
    assert r.injection_seq is not None
    assert r.injection_verified is True
    by_agent = {e.agent: e.payload.get("model_id")
                for e in r.trace.events if e.kind == "agent-msg"}
    assert by_agent["extractor"] == DOWNGRADE_MODEL       # worker on the downgraded id
    assert by_agent["reviewer"] == PIPELINE_MODEL          # reviewer stays on-tier


def test_o4_verified_false_when_model_id_absent():
    class NoStampAdapter(Wave2LangGraphAdapter):
        _build_models = LangGraphAdapter._build_models     # wave-1 clients: no stamping
    r = NoStampAdapter(tasks_dir=TASKS, model_factory=_o4_factory).run(_cell("T1", "O4"))
    assert r.error is None
    assert all("model_id" not in e.payload
               for e in r.trace.events if e.kind == "agent-msg")
    assert r.injection_verified is False
    # the frozen wave-1 adapter records the same cell verified unconditionally — the
    # flip above is the v0.2 correction, not a behavior change in the base.
    r1 = LangGraphAdapter(tasks_dir=TASKS, model_factory=_o4_factory).run(_cell("T1", "O4"))
    assert r1.injection_verified is True


def test_o4_verified_false_when_model_id_wrong():
    class WrongStampAdapter(Wave2LangGraphAdapter):
        def _build_models(self, injector, agent):
            worker, reviewer = super()._build_models(injector, agent)
            worker._model_id = PIPELINE_MODEL              # stage records an on-tier id
            return worker, reviewer
    r = WrongStampAdapter(tasks_dir=TASKS, model_factory=_o4_factory).run(_cell("T1", "O4"))
    assert r.error is None
    assert not any(e.payload.get("model_id") == DOWNGRADE_MODEL
                   for e in r.trace.events if e.kind == "agent-msg")
    assert r.injection_verified is False
