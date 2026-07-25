import json, pathlib
import pytest
pytest.importorskip("langchain_openai")  # this venv may be .venv-crewai/.venv-autogen
from sabot.runner import Cell
from sabot.adapters.langgraph_adapter import LangGraphAdapter
from sabot.adapters.operator_specs import SPECS, DOWNGRADE_MODEL

TASKS = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "tasks").is_dir() and (p / "SPEC.md").is_file()) / "tasks"
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
T4_BAD_PLAN_UNKNOWN_TOKEN = json.dumps([
    "depart_base", "visit:Nowhere", "return_base",
])

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


def _cell(task, config="default", operator=None, spec=None, seed=1):
    return Cell(framework="langgraph", task=task, config=config,
               operator=operator, operator_spec=spec, seed=seed)


# --- operator_specs.py completeness (Task 6 Part A) -------------------------------------

def test_specs_cover_all_30_pairs_and_o4_carries_downgrade():
    tasks = ["T1", "T2", "T3", "T4", "T5"]
    operators = ["O1", "O2", "O3", "O4", "O5", "O6"]
    assert set(SPECS) == {(t, o) for t in tasks for o in operators}
    for t in tasks:
        assert SPECS[(t, "O4")] == {"downgrade_to": DOWNGRADE_MODEL}


def test_o1_find_strings_occur_in_their_source_asset_or_construction():
    t1_src = (TASKS / "assets" / "T1-source.md").read_text()
    t2_src = (TASKS / "assets" / "T2-sources.md").read_text()
    t3_src = (TASKS / "T3-codegen-review.md").read_text()
    t4_src = LangGraphAdapter._t4_route_context()
    t5_src = (TASKS / "assets" / "T5-corpus.md").read_text()
    assert SPECS[("T1", "O1")]["find"] in t1_src
    assert SPECS[("T2", "O1")]["find"] in t2_src
    assert SPECS[("T3", "O1")]["find"] in t3_src
    assert SPECS[("T4", "O1")]["find"] in t4_src
    assert SPECS[("T5", "O1")]["find"] in t5_src


def test_o3_find_strings_occur_in_their_source_asset_or_handoff_construction():
    t1_src = (TASKS / "assets" / "T1-source.md").read_text()
    t2_src = (TASKS / "assets" / "T2-sources.md").read_text()
    t3_src = (TASKS / "assets" / "T3_test_suite.py").read_text()
    t4_src = (TASKS / "assets" / "T4_constraints_check.py").read_text()
    t5_src = (TASKS / "assets" / "T5-corpus.md").read_text()
    assert SPECS[("T1", "O3")]["find"] in t1_src
    assert SPECS[("T2", "O3")]["find"] in t2_src
    assert SPECS[("T3", "O3")]["find"] in t3_src
    assert SPECS[("T4", "O3")]["find"] in t4_src
    assert SPECS[("T5", "O3")]["find"] in t5_src


# --- T1 (pilot, extended with guardrail config) ------------------------------------------

def test_baseline_t1_happy_path_scores_pass():
    a = _adapter([json.dumps(GOLDEN), "VERDICT: APPROVE"])
    r = a.run(_cell("T1"))
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
    r = a.run(_cell("T1", operator="O1", spec=SPECS[("T1", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("74.1" in p for p in seen_prompts)          # fault reached the model input
    hard = [e for e in r.trace.events
            if e.kind == "guardrail-event" and e.payload["act"] == "reject"]
    assert hard and hard[0].seq >= r.injection_seq


def test_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([json.dumps(GOLDEN), "VERDICT: REJECT - check the caption",
                  json.dumps(GOLDEN), "VERDICT: APPROVE"])
    r = a.run(_cell("T1"))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t1_guardrail_validator_rejects_then_revise_recovers():
    missing_key = dict(GOLDEN); del missing_key["inspector_name"]
    a = _adapter([json.dumps(missing_key), "VERDICT: APPROVE",
                  json.dumps(GOLDEN), "VERDICT: APPROVE"])
    r = a.run(_cell("T1", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "reject") in acts
    assert ("validator", "retry_with_reason") in acts
    assert r.task_passed is True and r.error is None


def test_t1_guardrail_escalates_and_terminates_on_second_validator_failure():
    missing_key = dict(GOLDEN); del missing_key["inspector_name"]
    a = _adapter([json.dumps(missing_key), "VERDICT: APPROVE",
                  json.dumps(missing_key), "VERDICT: APPROVE"])
    r = a.run(_cell("T1", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "escalate") in acts
    assert r.task_passed is False and r.error is None


# --- T2 research-review -------------------------------------------------------------------

def test_baseline_t2_happy_path_scores_pass():
    a = _adapter([T2_GOOD_SUMMARY, "VERDICT: APPROVE"])
    r = a.run(_cell("T2"))
    assert r.error is None and r.task_passed is True


def test_t2_o1_injection_lands_in_real_graph_data_path():
    seen_prompts = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen_prompts.append(str(input))
            return super().invoke(input)
    a = LangGraphAdapter(tasks_dir=TASKS,
                         model_factory=lambda m: SpyModel([T2_GOOD_SUMMARY,
                                                           "VERDICT: APPROVE"]))
    r = a.run(_cell("T2", operator="O1", spec=SPECS[("T2", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("4,800" in p for p in seen_prompts)


def test_t2_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([T2_GOOD_SUMMARY, "VERDICT: REJECT - check the audit",
                  T2_GOOD_SUMMARY, "VERDICT: APPROVE"])
    r = a.run(_cell("T2"))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t2_guardrail_validator_rejects_then_revise_recovers():
    a = _adapter([T2_BAD_SUMMARY_MISSING_COST, "VERDICT: APPROVE",
                  T2_GOOD_SUMMARY, "VERDICT: APPROVE"])
    r = a.run(_cell("T2", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "reject") in acts
    assert r.task_passed is True and r.error is None


def test_t2_guardrail_escalates_and_terminates_on_second_validator_failure():
    a = _adapter([T2_BAD_SUMMARY_MISSING_COST, "VERDICT: APPROVE",
                  T2_BAD_SUMMARY_MISSING_COST, "VERDICT: APPROVE"])
    r = a.run(_cell("T2", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "escalate") in acts
    assert r.task_passed is False and r.error is None


# --- T3 codegen-review ---------------------------------------------------------------------

def test_baseline_t3_happy_path_scores_pass():
    a = _adapter([T3_GOOD_SOLUTION, "VERDICT: APPROVE"])
    r = a.run(_cell("T3"))
    assert r.error is None and r.task_passed is True


def test_t3_o1_injection_lands_in_real_graph_data_path():
    seen_prompts = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen_prompts.append(str(input))
            return super().invoke(input)
    a = LangGraphAdapter(tasks_dir=TASKS,
                         model_factory=lambda m: SpyModel([T3_GOOD_SOLUTION,
                                                           "VERDICT: APPROVE"]))
    r = a.run(_cell("T3", operator="O1", spec=SPECS[("T3", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("5.57" in p for p in seen_prompts)


def test_t3_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([T3_GOOD_SOLUTION, "VERDICT: REJECT - check the highland waiver",
                  T3_GOOD_SOLUTION, "VERDICT: APPROVE"])
    r = a.run(_cell("T3"))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t3_guardrail_validator_rejects_then_revise_recovers():
    a = _adapter([T3_BAD_SOLUTION_WRONG_SYMBOL, "VERDICT: APPROVE",
                  T3_GOOD_SOLUTION, "VERDICT: APPROVE"])
    r = a.run(_cell("T3", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "reject") in acts
    assert r.task_passed is True and r.error is None


def test_t3_guardrail_escalates_and_terminates_on_second_validator_failure():
    a = _adapter([T3_BAD_SOLUTION_WRONG_SYMBOL, "VERDICT: APPROVE",
                  T3_BAD_SOLUTION_WRONG_SYMBOL, "VERDICT: APPROVE"])
    r = a.run(_cell("T3", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "escalate") in acts
    assert r.task_passed is False and r.error is None


# --- T4 planning-tools -----------------------------------------------------------------------

def test_baseline_t4_happy_path_scores_pass():
    a = _adapter([T4_GOOD_PLAN, "VERDICT: APPROVE"])
    r = a.run(_cell("T4"))
    assert r.error is None and r.task_passed is True


def test_t4_o1_injection_lands_in_real_graph_data_path():
    seen_prompts = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen_prompts.append(str(input))
            return super().invoke(input)
    a = LangGraphAdapter(tasks_dir=TASKS,
                         model_factory=lambda m: SpyModel([T4_GOOD_PLAN,
                                                           "VERDICT: APPROVE"]))
    r = a.run(_cell("T4", operator="O1", spec=SPECS[("T4", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("40 km" in p for p in seen_prompts)


def test_t4_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([T4_GOOD_PLAN, "VERDICT: REJECT - check the fuel range",
                  T4_GOOD_PLAN, "VERDICT: APPROVE"])
    r = a.run(_cell("T4"))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t4_guardrail_validator_rejects_then_revise_recovers():
    a = _adapter([T4_BAD_PLAN_UNKNOWN_TOKEN, "VERDICT: APPROVE",
                  T4_GOOD_PLAN, "VERDICT: APPROVE"])
    r = a.run(_cell("T4", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "reject") in acts
    assert r.task_passed is True and r.error is None


def test_t4_guardrail_escalates_and_terminates_on_second_validator_failure():
    a = _adapter([T4_BAD_PLAN_UNKNOWN_TOKEN, "VERDICT: APPROVE",
                  T4_BAD_PLAN_UNKNOWN_TOKEN, "VERDICT: APPROVE"])
    r = a.run(_cell("T4", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "escalate") in acts
    assert r.task_passed is False and r.error is None


# --- T5 docqa-citations ------------------------------------------------------------------------

def test_baseline_t5_happy_path_scores_pass():
    a = _adapter([T5_GOOD_ANSWER, "VERDICT: APPROVE"])
    r = a.run(_cell("T5"))
    assert r.error is None and r.task_passed is True


def test_t5_o1_injection_lands_in_real_graph_data_path():
    seen_prompts = []
    class SpyModel(ScriptedModel):
        def invoke(self, input):
            seen_prompts.append(str(input))
            return super().invoke(input)
    a = LangGraphAdapter(tasks_dir=TASKS,
                         model_factory=lambda m: SpyModel([T5_GOOD_ANSWER,
                                                           "VERDICT: APPROVE"]))
    r = a.run(_cell("T5", operator="O1", spec=SPECS[("T5", "O1")]))
    assert r.injection_verified is True and r.injection_seq is not None
    assert any("1.6 metres" in p for p in seen_prompts)


def test_t5_reviewer_reject_routes_to_revise_then_emits():
    a = _adapter([T5_GOOD_ANSWER, "VERDICT: REJECT - check the citation",
                  T5_GOOD_ANSWER, "VERDICT: APPROVE"])
    r = a.run(_cell("T5"))
    acts = [e.payload["act"] for e in r.trace.events if e.kind == "guardrail-event"]
    assert "reject" in acts and "retry_with_reason" in acts
    assert r.task_passed is True


def test_t5_guardrail_validator_rejects_then_revise_recovers():
    a = _adapter([T5_BAD_ANSWER_EMPTY_CITATIONS, "VERDICT: APPROVE",
                  T5_GOOD_ANSWER, "VERDICT: APPROVE"])
    r = a.run(_cell("T5", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "reject") in acts
    assert r.task_passed is True and r.error is None


def test_t5_guardrail_escalates_and_terminates_on_second_validator_failure():
    a = _adapter([T5_BAD_ANSWER_EMPTY_CITATIONS, "VERDICT: APPROVE",
                  T5_BAD_ANSWER_EMPTY_CITATIONS, "VERDICT: APPROVE"])
    r = a.run(_cell("T5", config="guardrail"))
    acts = [(e.payload["component"], e.payload["act"]) for e in r.trace.events
            if e.kind == "guardrail-event"]
    assert ("validator", "escalate") in acts
    assert r.task_passed is False and r.error is None
