# CrewAI — doc-pull evidence (fetched live 2026-07-22)

Pulled live 2026-07-22 from PyPI JSON, context7 (/crewaiinc/crewai, docs v1.15.2 + edge),
and docs.crewai.com. Adapter code is written against THIS file, never memory.

## Versions (pin these)
- `crewai==1.15.5` (PyPI stable). Python >=3.10,<3.14.
- Breaking changes in current 1.x (official migration guide): tool imports moved to
  `from crewai.tools import BaseTool, tool`; `Agent.verbose` is bool;
  `Process.hierarchical` now REQUIRES `manager_llm=` or `manager_agent=`;
  `allow_delegation` disabled by default; set `max_iter` explicitly.

## Task guardrails (counted surface: "guardrail callbacks")
- `Task(guardrail=<callable|str>)` or `Task(guardrails=[...])` (list takes precedence;
  runs sequentially, each receives previous output; function + LLM-string mixable).
- Function guardrail signature (verified in doc AND source):
  `def g(result: TaskOutput) -> Tuple[bool, Any]` — `(True, validated_result)` or
  `(False, error_message_str)`. Exactly one parameter.
- On `(False, error)`: error is fed back to the agent, which retries — loop until True or
  `guardrail_max_retries` (default 3) exhausted. Terminal behavior at exhaustion is NOT
  documented (flagged gap — implementer verifies empirically in the pilot and records it).
- LLM guardrail: pass a string description → auto-built `LLMGuardrail` using the task
  agent's LLM; `__call__(task_output) -> tuple[bool, Any]`.
- Events fire around it: `LLMGuardrailStartedEvent / CompletedEvent / FailedEvent`.
- Docs: docs.crewai.com/en/concepts/tasks; source lib/crewai/src/crewai/tasks/llm_guardrail.py

## Events / observability (trace recorder seam)
- Canonical import: `from crewai.events import BaseEventListener` plus event classes
  (NOT crewai.utilities.events).
- Listener pattern: subclass `BaseEventListener`, implement
  `setup_listeners(self, crewai_event_bus)`, register with
  `@crewai_event_bus.on(EventClass)` — handlers receive `(source, event)`.
- Tool seam events: `ToolUsageStartedEvent`, `ToolUsageFinishedEvent`,
  `ToolUsageErrorEvent` — fire for EVERY tool call incl. delegation tools.
- Other relevant: `TaskStartedEvent/CompletedEvent/FailedEvent`,
  `AgentExecutionStartedEvent/CompletedEvent/ErrorEvent`,
  `LLMCallStartedEvent/CompletedEvent/FailedEvent`, `CrewKickoffStartedEvent/...`.
- Crew-level callbacks: `Crew(task_callback=..., step_callback=...)`.
- Docs: docs.crewai.com/en/concepts/event-listener

## Hierarchical / manager (SPEC §5 GAP — amendment required)
- `Crew(process=Process.hierarchical, manager_llm=... | manager_agent=...)` (one required).
- **NO dedicated "manager reassignment" or "anomaly reason" event exists.** Delegation is
  an ordinary tool call: `DelegateWorkTool` (name "Delegate work to coworker",
  `_run(task, context, coworker)`) / `AskQuestionTool` — observable via ToolUsage*Event
  filtered by tool_name, args carry task/context/coworker. No structured reason field;
  any "reason" lives in manager LLM free text. SPEC §5's "manager-agent reassignment
  carrying an anomaly reason" cannot be adjudicated deterministically → move to soft tier
  via v0.1.1 amendment (plan Task 9).

## Model config (O4 seam)
- `from crewai import LLM` — `LLM(model="openai/gpt-5.6-terra", temperature=0.0)`
  (LiteLLM provider/model format; needs OPENAI_API_KEY or api_key=).
- `Agent(llm=<LLM|str>)` — per-agent constructor injection; mixed-LLM crews are a
  documented first-class pattern. O4 = build the one Agent with a different LLM instance.

## Tool wrapping (O1/O2/O6 seam)
- `from crewai.tools import BaseTool, tool` (current path).
- Class form: subclass BaseTool with `name`, `description`, `args_schema`, `def _run(...)`.
  **`_run` is the wrap point**; non-invasive alternative = ToolUsageFinishedEvent handler.
- Decorator: `@tool("Name")` over a plain function.

## Human input
- `Task(human_input=True)` = blocking stdin prompt; NO documented programmatic answer
  channel. Do not use human_input in pipelines (headless benchmark).

## Structured output
- `Task(output_pydantic=ModelClass)` / `output_json=ModelClass` — schema validation.
- No built-in reviewer/QA agent stage beyond guardrails; enterprise "hallucination
  guardrail" raises ValidationError(feedback) but is enterprise-tier — out of scope.

## FLAGGED GAPS (verify empirically during build, record findings)
1. Terminal behavior when guardrail_max_retries exhausts (OSS path).
2. Whether human_input can be answered programmatically (moot — we don't use it).
3. Whether Flow-level human-feedback events fire for Task.human_input (moot).
