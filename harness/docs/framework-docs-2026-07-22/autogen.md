# AutoGen / Magentic-One — doc-pull evidence (fetched live 2026-07-22)

Pulled live 2026-07-22 from PyPI JSON, context7 (microsoft.github.io/autogen stable docs +
github.com/microsoft/agent-framework), and raw GitHub source. Adapter code is written
against THIS file, never memory.

## HEADLINE: lineage status + pin decision
- AutoGen (autogen-agentchat/-core/-ext) is in MAINTENANCE MODE: latest 0.7.5 released
  2025-09-30, nothing since. Microsoft converged AutoGen + Semantic Kernel into
  "Microsoft Agent Framework" (`agent-framework`, 1.0 GA 2026-04-02; 1.12.0 released
  2026-07-21 — actively moving). Corroborated via devblogs.microsoft.com/agent-framework,
  visualstudiomagazine.com, learn.microsoft.com/en-us/agent-framework/overview (secondary
  sources; no PyPI-level deprecation banner).
- PIN DECISION (recommended, Jeff gates at plan approval): `autogen-agentchat==0.7.5`,
  `autogen-core==0.7.5`, `autogen-ext[openai]==0.7.5`. Rationale: frozen API =
  reproducibility; only lineage with doc-verified Magentic-One ledger internals; SPEC §5
  names "AutoGen / Magentic-One". agent-framework's Magentic observability depth is an
  open research gap (builder API confirmed, internals not). Scoreboard writeup carries an
  honest maintenance-mode note; agent-framework = named wave-2 candidate.
- Never pin autogen below 0.4.2 (yanked GPL-dep versions).
- Magentic-One extras pull playwright/markitdown/magika — only needed for the bundled web/
  file agents, which we do NOT use (our own task agents only).

## Teams (pipeline shapes)
- `from autogen_agentchat.teams import RoundRobinGroupChat` —
  `RoundRobinGroupChat(participants, *, name=None, description=None,
  termination_condition=None, max_turns=None, runtime=None,
  custom_message_types=None, emit_team_events=False)`.
- `from autogen_agentchat.teams import MagenticOneGroupChat` —
  `MagenticOneGroupChat(participants, model_client, *, name=None, description=None,
  termination_condition=None, max_turns=20, runtime=None, max_stalls=3,
  final_answer_prompt=..., custom_message_types=None, emit_team_events=False)`.
  Orchestrator name string = "MagenticOneOrchestrator" (filter stream by .source).
  NOTE: orchestrator takes its OWN model_client, distinct from participants' clients.
- `SelectorGroupChat(participants, model_client=..., termination_condition=...,
  selector_prompt=..., allow_repeated_speaker=...)` (full signature not pulled; fetch
  _selector_group_chat source if needed).
- Set `emit_team_events=True` in the harness to surface SelectSpeakerEvent etc.

## Magentic-One internals (counted surface: "orchestrator re-planning")
- State schema (doc-verified): MagenticOneOrchestratorState{task, facts, plan, n_rounds,
  n_stalls, type}.
- Stall/replan logic (from MAIN-branch source — RE-VERIFY against the 0.7.5 sdist before
  hard-coding): progress ledger dict with required keys
  ["is_request_satisfied","is_progress_being_made","is_in_loop",
   "instruction_or_question","next_speaker"]; `_n_stalls` incremented on
  no-progress/in-loop, on `_n_stalls >= _max_stalls` → "Stall count exceeded,
  re-planning..." → `_update_task_ledger` → `_reenter_outer_loop`.
- OBSERVABILITY: no dedicated ReplanEvent class. Re-plan surfaces as a TextMessage with
  source "MagenticOneOrchestrator" (rebuilt task-ledger prompt). Raw progress-ledger dict
  (structured booleans) goes to Python logging TRACE_LOGGER_NAME — hook the logger for
  deterministic signal rather than string-matching message content.
- Completion: `_signal_termination(StopMessage(content=reason, source=self._name))`.

## Termination (counted surface: "termination messages citing anomaly")
- `from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination,
  HandoffTermination, ExternalTermination, SourceMatchTermination, TokenUsageTermination`.
  Composable with `|`. `FunctionCallTermination` is a tutorial EXAMPLE — check
  `conditions.__all__` in 0.7.5 before importing.
- `TaskResult` (pydantic): `.messages`, `.stop_reason: str | None` — run_stream yields
  events then a final TaskResult; detect via isinstance.

## Critic pattern (counted surface: "critic-agent negative verdicts")
- Canonical doc pattern: `RoundRobinGroupChat([primary, critic],
  termination_condition=TextMentionTermination("APPROVE"))`; critic system message
  instructs "Respond with 'APPROVE' when addressed." Negative verdict = ordinary
  TextMessage from critic source WITHOUT the token — no dedicated event class; harness
  adjudicates by published token protocol (deterministic parse).
- Structured alternative: `DiGraphBuilder`/`GraphFlow` with
  `add_edge(a, b, condition=lambda msg: "APPROVE" in msg.to_model_text())`.

## Messages / streaming (trace recorder seam)
- `from autogen_agentchat.messages import TextMessage, MultiModalMessage, StopMessage,
  ToolCallSummaryMessage, HandoffMessage, ToolCallRequestEvent, ToolCallExecutionEvent,
  MemoryQueryEvent, UserInputRequestedEvent, ModelClientStreamingChunkEvent, ThoughtEvent,
  SelectSpeakerEvent, CodeGenerationEvent, CodeExecutionEvent, BaseAgentEvent,
  BaseChatMessage`.
- Team: `run_stream(task, ...) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage |
  TaskResult]`. Agent: `on_messages_stream(...)`. Tool round-trips also appear in
  `Response.inner_messages`.

## Model config (O4 seam)
- `from autogen_ext.models.openai import OpenAIChatCompletionClient` —
  `OpenAIChatCompletionClient(model="gpt-5.6-terra", temperature=0)`; per-agent injection
  via each `AssistantAgent(name, model_client=...)`; orchestrator client is separate.
- For model ids unknown to autogen's registry pass
  `model_capabilities={"vision":..., "function_calling":..., "json_output":...}` (doc:
  core-user-guide/faqs) — expect to need this for gpt-5.6-terra; verify at pilot.

## Tool wrapping (O1/O2/O6 seam)
- `from autogen_core.tools import FunctionTool` —
  `FunctionTool(func, description, name=None, global_imports=[], strict=False)`.
- Seams: wrap the plain Python func BEFORE FunctionTool construction (simplest);
  `run_json` validates+executes+logs (emits ToolCallRequestEvent/ToolCallExecutionEvent);
  `return_value_as_string(value)` = what the LLM sees. No built-in middleware hook.

## FLAGS
1. Magentic internals came from MAIN branch — re-verify against 0.7.5 before wiring.
2. agent-framework Magentic ledger observability = open gap (not confirmed absent).
3. "Maintenance mode" is well-corroborated secondary-source, not a PyPI banner.

## CORRECTION (2026-07-22, Task 8 Step 1 — installed 0.7.5 re-verification)

Re-verified against the INSTALLED `autogen-agentchat==0.7.5` package (package-local
equivalent of the sdist):
`.venv-autogen/lib/python3.11/site-packages/autogen_agentchat/teams/_group_chat/_magentic_one/_magentic_one_orchestrator.py`.

1. **Re-plan log string.** This file's "Stall/replan logic" section above paraphrases the
   re-plan log line as "Stall count exceeded, re-planning...". The installed 0.7.5 source's
   EXACT string (`_orchestrate_step`, the `_log_message(...)` call immediately before
   `_update_task_ledger`/`_reenter_outer_loop`) is:

       "Stall count exceeded, re-planning with the outer loop..."

   Everything else in the "Magentic-One internals" section above (progress-ledger required
   keys, `TRACE_LOGGER_NAME`, stall-counting logic, `_signal_termination(StopMessage(...))`)
   matches the installed source verbatim — no other correction needed.

2. **Stalling does not terminate the run.** Confirmed by reading `_orchestrate_step`:
   `_n_stalls >= _max_stalls` triggers `_update_task_ledger` + `_reenter_outer_loop` (a
   re-plan), not `_signal_termination`. The group chat keeps running. The only routes to a
   real `TaskResult.stop_reason` in 0.7.5 are `is_request_satisfied: true` (normal
   completion) or `max_turns` exceeded ("Max rounds reached."). There is no dedicated
   stall-exhaustion `StopMessage` variant — the re-plan is observable ONLY via the
   trace-logger hook, never via `stop_reason`.

3. **Model-config kwarg name (Model config / O4 seam section above).** This file's earlier
   text says `model_capabilities={...}` for models unknown to autogen's registry. Installed
   `autogen_ext/models/openai/_openai_client.py` shows `model_capabilities` is DEPRECATED
   (`"model_capabilities is deprecated, use model_info instead"`, still functionally
   accepted but warns) — the current, non-deprecated kwarg is `model_info` (a `ModelInfo`
   dict; required fields per `autogen_core.models._model_client.validate_model_info`:
   `vision`, `function_calling`, `json_output`, `family`, plus `structured_output`
   warned-if-absent). The adapter uses `model_info=`, not `model_capabilities=`.

4. **Offline replay client confirmed present.** `autogen_ext.models.replay.ReplayChatCompletionClient(chat_completions=[...], model_info=None)`
   ships in 0.7.5 (this file's "FLAGS" section left this as an open question for the
   implementer to verify) — confirmed present by installed-source inspection, used directly
   as the adapter's offline test seam, no additional stub needed.
