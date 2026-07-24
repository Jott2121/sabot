"""Wave-2 (SPEC v0.2.0 §10) CrewAI adapter — extends the frozen wave-1 CrewAIAdapter.

Three additions, each a §10 instrument change, none of which touches a wave-1 code path
(the base adapter behaves byte-identically when these hooks are unused):

  1. §10.2 anomaly-first reviewer addendum on ALL five tasks' reviewer system prompts.
     The pilot ProbeCrewAIAdapter covered T1/T2/T3/T5; wave 2 adds T4, so every
     reviewer-bearing cell in both configs carries it (the reviewer stage runs in both).
     The verdict-token parse is position-independent, so every wave-1 surface (acts,
     guardrails, scoring) is untouched; the FLAGS text reaches the trace via the existing
     reviewer agent-msg/verdict events and is adjudicated post-hoc by
     wave2.scan_trace_flags_v2.

  2. §10.7.1 T2 deterministic guardrail restructured to structural checks
     (wave2.t2_structural_check), closing the wave-1 fairness-rule asymmetry (RESULTS
     footnote 7) where the T2 contract's required substrings were canonical answer
     VALUES. Only T2's deterministic guardrail entry changes; the T2 LLM-guardrail entry
     built alongside it in _run_pipeline and every other task's guardrail are untouched.

  3. §10.7.2 O4 landing probe. Each stage records the model id actually serving it into
     its agent-msg payload ("model_id"); an O4 cell whose downgraded client served no
     call at/after the injection is INJECTION_UNVERIFIED — wave 1 recorded O4 verified
     unconditionally (QC conformance finding 6). run() recomputes injection_verified for
     O4 via wave2.o4_landed over the recorded trace.
"""
from __future__ import annotations

from sabot import wave2
from sabot.adapters.crewai_adapter import CrewAIAdapter, _RunListener
from sabot.adapters.recorder import TraceRecorder
from sabot.runner import Cell, RunResult

# The wave-1 LLM factory builds `openai/<id>` clients; O4's downgrade target is expressed
# as the bare id (operator_specs.DOWNGRADE_MODEL), so the landing probe compares bare ids.
_OPENAI_PREFIX = "openai/"


class Wave2CrewAIAdapter(CrewAIAdapter):
    # §10.2 — anomaly-first addendum on every reviewer system prompt, all five tasks.
    _T1_REVIEWER_SYS = CrewAIAdapter._T1_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T2_REVIEWER_SYS = CrewAIAdapter._T2_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T3_REVIEWER_SYS = CrewAIAdapter._T3_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T4_REVIEWER_SYS = CrewAIAdapter._T4_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T5_REVIEWER_SYS = CrewAIAdapter._T5_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM

    # §10.7.1 — swap ONLY T2's deterministic guardrail for the structural check. The LLM
    # guardrail entry (llm_guardrail_desc) that _run_pipeline builds alongside it stays.
    def _t2_contract_fn(self):
        def check_t2_structural(result):
            ok, reason = wave2.t2_structural_check(result.raw or "")
            return (True, result.raw) if ok else (False, reason)
        return check_t2_structural

    # §10.7.2 — attach the model-id resolver so each stage's agent-msg records the model
    # that served it (the base listener records none, preserving wave-1 payloads).
    def _make_listener(self, rec: TraceRecorder) -> _RunListener:
        return _RunListener(rec, model_id_of=self._stage_model_id)

    @staticmethod
    def _stage_model_id(agent) -> str | None:
        model = getattr(getattr(agent, "llm", None), "model", None)
        if isinstance(model, str) and model.startswith(_OPENAI_PREFIX):
            return model[len(_OPENAI_PREFIX):]
        return model

    def run(self, cell: Cell) -> RunResult:
        result = super().run(cell)
        if cell.operator != "O4":
            return result
        landed = wave2.o4_landed([e.to_dict() for e in result.trace.events],
                                 cell.operator_spec["downgrade_to"],
                                 result.injection_seq or 0)
        return RunResult(trace=result.trace, task_passed=result.task_passed,
                         injection_seq=result.injection_seq,
                         injection_verified=result.injection_verified and landed,
                         error=result.error)
