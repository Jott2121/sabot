# Sabot

**Crash-test ratings for agent stacks.** Sabot plants controlled faults inside a running
agent pipeline and scores what fraction of them the pipeline's **own** checks catch.

Every serious agent framework ships self-verification: reviewer agents, critic stages,
guardrail callbacks, voting. The industry's reliability story rests on those checks
working. Sabot is a standard (a frozen metric spec), a harness (a runnable tool), and a
public scoreboard measuring whether they do.

## The metric in one paragraph

Each planted fault gets three ordered verdicts — **DETECTED** (a component of the
pipeline itself flagged it), **REACTED** (the pipeline acted on the flag), **RECOVERED**
(the task still ended correct). The headline **Sabot Score** is the hard-tier detection
rate: only detection *acts* recorded by the framework's own surfaces count, adjudicated
deterministically against the published per-framework mapping in [SPEC.md](SPEC.md). A
cross-lineage LLM judge separately scores "noticed but not acted on" (the soft tier);
the gap between them — faults an agent saw and the system overrode — is published as its
own number. Full definitions, operators, mappings, and pre-registered interpretation
bands: [SPEC.md](SPEC.md).

## Status

- **2026-07-22:** SPEC v0.1 published. First scoreboard (LangGraph, CrewAI,
  AutoGen/Magentic-One) in progress; harness and raw traces publish here with the
  results. Interpretation bands are pre-registered in SPEC §7 *before* any data exists,
  and results publish regardless of what they show.

## Standing on prior work

Sabot invents neither fault injection for agents nor agent-level mutation scoring. It is
a synthesis, measured comparatively at production scale: MAS-FIRE (arXiv 2602.19843)
established own-mechanism detection rates over injected faults on academic systems;
AgentAssay (arXiv 2603.02601) formalized an agent mutation score including model-swap
operators under external adjudication; AgentTelemetry (AIware 2026), AgentCollabBench
(arXiv 2605.08647), ReliabilityBench (arXiv 2601.06112), AutoInject (arXiv 2408.00989),
the "Failing Tools" benchmark (OpenReview j7YsSnA64D), and the chaos tools agent-chaos
and BalaganAgent occupy adjacent ground, credited in SPEC §9. What did not exist before
Sabot: a named comparative standard that separates
detected from reacted, attributes detection to named guardrail components, and publishes
framework-vs-framework results anyone can reproduce.

## Author

Jeff Otterson — [The Oracle Gate](https://github.com/Jott2121/oracle-gate) ·
[crucible](https://github.com/Jott2121/crucible)
