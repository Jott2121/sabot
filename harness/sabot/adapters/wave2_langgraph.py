"""Wave-2 (SPEC v0.2.0) adapter — LangGraph. Three changes from the frozen wave-1
adapter, nothing else:

1. SPEC 10.2 — every reviewer system prompt (all five tasks) gains the anomaly-first
   REVIEWER_ADDENDUM, exactly like the pilot's CrewAI probe (probe_crewai.py). The
   base adapter uses one `_T?_REVIEWER_SYS` per task for BOTH configs (default and
   guardrail share the review node), so the class-attribute override lands the
   addendum in both. The verdict-token parse is position-independent, so all wave-1
   surfaces are untouched; FLAGS text reaches the trace via the existing reviewer
   agent-msg events and is adjudicated post-hoc by wave2.scan_trace_flags_v2.
2. SPEC 10.7.1 — the T2 deterministic guardrail is restructured to structural checks
   (wave2.t2_structural_check): format presence, never canonical answer VALUES. The
   swap happens at the `_wire_and_run` seam, so it applies only where a validate node
   exists (guardrail config) and only for T2; every other task keeps its wave-1
   validator verbatim.
3. SPEC 10.7.2 — the O4 landing probe. Each LLM client is wrapped so the agent-msg
   recording its reply carries "model_id": the id the client was built with
   (including the O4 model_override path). run() then re-adjudicates O4 cells:
   injection_verified holds only if wave2.o4_landed finds the downgraded model
   actually serving a call at/after the injection — wave-1 recorded O4 verified
   unconditionally (QC conformance finding 6)."""
from __future__ import annotations
from sabot import wave2
from sabot.adapters.langgraph_adapter import LangGraphAdapter, PIPELINE_MODEL
from sabot.adapters.recorder import TraceRecorder
from sabot.runner import Cell, RunResult


class _Wave2Recorder(TraceRecorder):
    """One-shot model-id stamping: a client proxy arms the recorder right after each
    LLM call, and the NEXT agent-msg (the node factories record the model's reply as
    the immediately following agent-msg) carries that client's model id. One-shot
    consumption keeps non-LLM agent-msgs (the O6 fake tool report) unstamped, so
    every recorded model_id names a client that genuinely served that message."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._pending_model_id: str | None = None

    def arm_model_stamp(self, model_id: str) -> None:
        self._pending_model_id = model_id

    def agent_msg(self, agent: str, text: str) -> int:
        model_id, self._pending_model_id = self._pending_model_id, None
        if model_id is None:
            return super().agent_msg(agent, text)
        return self._emit("agent-msg", agent, {"text": text, "model_id": model_id})


class _StampedClient:
    """Invoke-only proxy around a pipeline model client. The node factories use the
    client solely via .invoke(), so nothing else needs delegating."""

    def __init__(self, inner, model_id: str, rec: _Wave2Recorder):
        self._inner = inner
        self._model_id = model_id
        self._rec = rec

    def invoke(self, input):
        resp = self._inner.invoke(input)
        self._rec.arm_model_stamp(self._model_id)
        return resp


def _t2_validate(state) -> tuple[bool, str]:
    return wave2.t2_structural_check(state.get("draft", ""))


class Wave2LangGraphAdapter(LangGraphAdapter):
    _recorder_cls = _Wave2Recorder

    _T1_REVIEWER_SYS = LangGraphAdapter._T1_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T2_REVIEWER_SYS = LangGraphAdapter._T2_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T3_REVIEWER_SYS = LangGraphAdapter._T3_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T4_REVIEWER_SYS = LangGraphAdapter._T4_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T5_REVIEWER_SYS = LangGraphAdapter._T5_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM

    def _build_models(self, injector, agent: str):
        # Same construction logic as the base (single injector.model_id call so O4
        # lands exactly once; ONE shared instance off the O4 path so offline
        # ScriptedModel fifo queues keep their wave-1 meaning) — each client wrapped
        # to stamp the agent-msg it serves (SPEC 10.7.2).
        rec = injector._rec
        worker_id = injector.model_id(agent, PIPELINE_MODEL)
        if worker_id == PIPELINE_MODEL:
            shared = _StampedClient(self._model_factory(PIPELINE_MODEL),
                                    PIPELINE_MODEL, rec)
            return shared, shared
        return (_StampedClient(self._model_factory(worker_id), worker_id, rec),
                _StampedClient(self._model_factory(PIPELINE_MODEL),
                               PIPELINE_MODEL, rec))

    def _wire_and_run(self, cell: Cell, rec, inj: dict, *, load_node,
                      worker_agent: str, worker_node, review_node, validate_fn,
                      emit_node) -> RunResult:
        if cell.task == "T2":
            validate_fn = _t2_validate      # SPEC 10.7.1; guardrail config only wires it
        return super()._wire_and_run(cell, rec, inj, load_node=load_node,
                                     worker_agent=worker_agent,
                                     worker_node=worker_node,
                                     review_node=review_node,
                                     validate_fn=validate_fn, emit_node=emit_node)

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
