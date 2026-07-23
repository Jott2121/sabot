# LangGraph — doc-pull evidence (fetched live 2026-07-22)

Every fact below was pulled from live docs/PyPI on 2026-07-22 (context7 + WebFetch of
docs.langchain.com / reference.langchain.com / pypi.org). Adapter code is written against
THIS file, never memory. Items under "UNVERIFIED" must be re-checked before use.

## Versions (pin these)
- `langgraph==1.2.9` (PyPI, released 2026-07-10). 1.0 shipped 2025-10-17 with a
  zero-breaking-changes policy; StateGraph core unchanged. 1.2 added per-node timeouts,
  node-level error handlers, DeltaChannel (beta).
- `langchain-openai==1.4.0` (release date not confirmed).
- Python 3.10+ required.

## Interrupts (counted surface: "interrupts")
- `from langgraph.types import interrupt` — `interrupt(value) -> Any`. Halts the node;
  value surfaces to caller. On resume the node re-executes FROM THE TOP (side effects
  before the interrupt re-run — not idempotent-safe).
- Resume / route: `from langgraph.types import Command` —
  `Command(*, graph=None, update=None, resume=None, goto=())`.
- Payload object: `from langgraph.types import Interrupt` — fields `value: Any`, `id: str`.
- OBSERVATION (verified twice): `result["__interrupt__"]` key in `.invoke()` output; in
  `stream_mode="updates"` the data dict can contain `__interrupt__` (tuple of Interrupt).
- Compile-time: `builder.compile(checkpointer=..., interrupt_before=[...], interrupt_after=[...])`.
- `langgraph.errors.NodeInterrupt` is DEPRECATED — do not build against it.
- Docs: docs.langchain.com/oss/python/langgraph/interrupts,
  reference.langchain.com/python/langgraph/types/interrupt

## Guardrail routing (counted surface: "explicit edge routing to error/review states")
- Node typed `Command[Literal["review_node", "next_node"]]` returns
  `Command(update={"error": "..."} , goto="review_node")` on failure — first-class documented
  pattern (docs.langchain.com/oss/python/langgraph/graph-api).
- `graph.add_conditional_edges(source, routing_fn, mapping=None)`; dynamic fan-out via
  `from langgraph.types import Send` — `Send(node_name, state)`.
- WARNING (verbatim from docs): Command only adds dynamic edges — static edges still
  execute; use either Command or static edges from a node, not both.

## Runtime observation
- Stream modes on `graph.stream()/astream()`: values, updates, messages, custom,
  checkpoints, tasks, debug. Multiple at once: `stream_mode=["updates","tasks"]`.
- `updates` carries per-node changed keys (and `__interrupt__`); `tasks` carries task
  start/finish incl. results/errors. Build the trace recorder on `["updates","tasks"]`.
- Docs: docs.langchain.com/oss/python/langgraph/streaming

## Checkpointing
- `from langgraph.checkpoint.memory import InMemorySaver` (MemorySaver is a plain alias).
- **"Checkpoint rejection" is NOT a real API concept** — confirmed absent from persistence
  docs. SPEC §5 wording must be amended (see plan Task 9).

## Model config (O4 seam)
- `from langchain_openai import ChatOpenAI` — `ChatOpenAI(model="gpt-5.6-terra", temperature=0)`;
  or `from langchain.chat_models import init_chat_model` — `init_chat_model("openai:gpt-5.6-terra", temperature=0)`.
- Per-agent override = construct a distinct model instance per node closure at graph-build
  time. No per-node model registry exists; the node function captures whatever the builder
  injects. O4 = swap the one node's model instance; assert the applied client's model id.

## Tool wrapping (O1/O2/O6 seam)
- `from langgraph.prebuilt import ToolNode` — NOT deprecated. Constructor:
  `ToolNode(tools, *, name='tools', tags=None, handle_tool_errors=<default>,
  messages_key='messages', wrap_tool_call: ToolCallWrapper | None = None,
  awrap_tool_call: AsyncToolCallWrapper | None = None)`.
  `wrap_tool_call` at construction = the interception seam; works on plain StateGraph
  (no create_agent middleware required).
- Tools defined via `@tool` from `langchain_core.tools`; tools may return `Command`.
- `create_agent` middleware alternative: `from langchain.agents.middleware import wrap_tool_call`
  (only fires for create_agent pipelines).

## Prebuilt agent status
- `langgraph.prebuilt.create_react_agent` DEPRECATED as of v1.0 → replacement
  `from langchain.agents import create_agent` (middleware system). Community confusion
  exists around the deprecation message (GH issue #6404). We build hand-rolled StateGraph
  pipelines, so this matters only if a reviewer asks why we didn't use prebuilts.

## Built-in guardrail middleware (best-guardrail config candidates)
- `from langchain.agents.middleware import PIIMiddleware` (strategy redact/mask/hash/block,
  `apply_to_tool_results=True` inspects tool outputs) and `HumanInTheLoopMiddleware`
  (`interrupt_on={...}`, rides on interrupt()/Command(resume)).
- Middleware fires ONLY for create_agent pipelines; hand-rolled StateGraph needs manual
  validator nodes + routing (which is what our pipelines use).

## UNVERIFIED — re-check before use
1. v1.2 "event streaming" typed-projection API exact shape
   (docs.langchain.com/oss/python/langgraph/event-streaming) — not confirmed; do not build
   on it, use stream_mode list instead.
2. SqliteSaver exact import path — not confirmed (we use InMemorySaver anyway).
3. langchain-openai 1.4.0 release date.
