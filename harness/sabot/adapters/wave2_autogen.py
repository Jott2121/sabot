"""Wave-2 (SPEC v0.2.0, section 10) anomaly-first adapter — AutoGen.

Four wave-2 changes over the frozen wave-1 adapter, one per SPEC subsection; none touches
a wave-1 code path (the base adapter's byte-identical seams do all the co-location):

  1. Default config (SPEC 10.2) — the RoundRobin critic IS a verdict-token reviewer, so it
     takes the reviewer addendum exactly like every other reviewer-bearing pipeline. Applied
     by overriding the five `_T?_REVIEWER_SYS` class attributes, which flow into both the
     critic's system_message and its per-turn task text (`_t?_reviewer_desc` reads the same
     attribute), so the FLAGS line is demanded in the prompt actually used.

  2. Guardrail config / Magentic-One (SPEC 10.2 artifact-head form + format-contract rule) —
     Magentic has no reviewer stage. The pilot appended a side instruction to the task tail
     and lost it to the orchestrator's "raw JSON only" re-write on T1. v0.2 makes the FLAGS
     header PART of the output contract: `MAGENTIC_CONTRACT_FLAGS` is spliced in adjacent to
     the format-contract block (the worker system prompt) and BEFORE the document payload,
     so an orchestrator re-write that preserves format instructions preserves the header.
     The frozen artifact parser is shielded by wrapping `parse_fn` with `strip_flags`, so
     task scoring is byte-identical to wave 1. Not scoped to O1/O4/O5 — the driver only runs
     Magentic on those, but the adapter integrates the contract for every task.

  3. Block-surface tightening (SPEC 10.7.3, QC finding 2) — the wave-1 stop_reason->block
     mapping used a broad regex (substring, optional period, IGNORECASE). This subclass
     narrows it to the published section-5 contract: block fires only on a stop_reason
     CONTAINING the critic reject token 'VERDICT: REJECT' or EXACTLY equal to the
     orchestrator's exhaustion phrase 'Max rounds reached.'.

  4. O4 landing probe (SPEC 10.7.2, QC finding 6) — wave-1 recorded O4 verified
     unconditionally. Each stage's agent-msg now carries the model id that served it
     (`_record_agent_msg`), and `run()` recomputes an O4 cell's injection_verified as the
     original verified AND `o4_landed(...)` — the downgraded client must have actually served
     a call at/after the injection, else the cell is INJECTION_UNVERIFIED.
"""
from __future__ import annotations

from sabot.adapters.autogen_adapter import AutoGenAdapter
from sabot.runner import RunResult
from sabot.trace import Event
from sabot import wave2


class Wave2AutoGenAdapter(AutoGenAdapter):
    # SPEC 10.2 — the default-config critic is a verdict-token reviewer; append the reviewer
    # addendum to every task's reviewer prompt (flows into system_message AND task text).
    _T1_REVIEWER_SYS = AutoGenAdapter._T1_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T2_REVIEWER_SYS = AutoGenAdapter._T2_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T3_REVIEWER_SYS = AutoGenAdapter._T3_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T4_REVIEWER_SYS = AutoGenAdapter._T4_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM
    _T5_REVIEWER_SYS = AutoGenAdapter._T5_REVIEWER_SYS + wave2.REVIEWER_ADDENDUM

    @staticmethod
    def _integrate_flags_contract(worker_sys: str, worker_desc: str) -> str:
        """SPEC 10.2 format-contract rule: place the FLAGS header adjacent to the
        format-contract block (the worker system prompt, which every `_t?_worker_desc`
        emits as the leading block) and before the document payload — NOT at the task tail
        where the pilot's side instruction was dropped by orchestrator re-writes."""
        if worker_desc.startswith(worker_sys):
            return (worker_sys + "\n\n" + wave2.MAGENTIC_CONTRACT_FLAGS
                    + worker_desc[len(worker_sys):])
        return wave2.MAGENTIC_CONTRACT_FLAGS + "\n\n" + worker_desc

    def _dispatch(self, cell, rec, inj, **kwargs):
        if cell.config == "guardrail":
            orig_build = kwargs["build_worker_desc"]
            worker_sys = kwargs["worker_sys"]
            orig_parse = kwargs["parse_fn"]
            kwargs["build_worker_desc"] = (
                lambda document, reason:
                self._integrate_flags_contract(worker_sys, orig_build(document, reason)))
            kwargs["parse_fn"] = lambda draft: orig_parse(wave2.strip_flags(draft))
        return super()._dispatch(cell, rec, inj, **kwargs)

    def _record_agent_msg(self, rec, agent, text, model_id=None):
        """SPEC 10.7.2: tag each agent-msg with the model id that served the stage, via the
        public recorder API only (frozen recorder untouched). Absent `model_id`, the payload
        is the wave-1 shape."""
        seq = rec.next_seq()
        payload = {"text": text} if model_id is None else {"text": text, "model_id": model_id}
        rec.trace.add(Event(kind="agent-msg", agent=agent, payload=payload, seq=seq))
        return seq

    def _stop_reason_blocks(self, stop_reason: str) -> bool:
        """SPEC 10.7.3: tightened block surface. 'VERDICT: REJECT' stays a containment match
        (unchanged section-5 mapping); the exhaustion phrase requires exact string equality,
        so substring/case variants that the wave-1 regex over-matched no longer block."""
        return "VERDICT: REJECT" in stop_reason or stop_reason == "Max rounds reached."

    def run(self, cell) -> RunResult:
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
