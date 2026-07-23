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
