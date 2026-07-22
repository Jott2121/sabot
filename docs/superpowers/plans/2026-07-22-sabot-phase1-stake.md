# Sabot Phase 1 — Public Stake + Metric Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the day-1 public stake — the `sabot` repo with the frozen metric SPEC, pre-registered bands, detection-act mappings, and task suite — and scaffold the private harness repo.

**Architecture:** Two repos. Public `Jott2121/sabot` holds the standard (SPEC.md is the product of this phase); private `sabot-harness` (local-only until reveal) holds code. All Phase-1 deliverables are authored documents plus scaffolding; the only executable code is the harness skeleton with its first passing test.

**Tech Stack:** Markdown + git + gh CLI (public repo); Python 3.11+, pytest, stdlib-only for the skeleton (deps arrive in Phase 2).

**Source of truth:** `~/sabot/docs/superpowers/specs/2026-07-22-sabot-design.md` (the approved design). Referred to below as DESIGN. Where a task says "transcribe DESIGN §N," the content already exists at that exact path and section — transcription with the noted adaptations is the work.

## Global Constraints

- Positioning rule (DESIGN §2) appears verbatim-in-spirit in every public artifact: Sabot is a synthesis citing MAS-FIRE (arXiv 2602.19843) and AgentAssay (arXiv 2603.02601); never claim invention of fault injection, agent mutation scores, or model-swap.
- Headline Sabot Score = hard-tier DETECTED rate only (DESIGN §3). Soft tier never blends into it.
- Pre-registered bands publish in the day-1 stake, before any data: median hard score < 0.50 → full push; >= 0.50 → publish with promo scaled down. Publish-regardless is absolute.
- Denominator = all valid injected faults; validity requires the no-fault baseline to pass; exclusions itemized, never silent. No "adjusted" scores.
- Dates absolute (YYYY-MM-DD). Public repo license: CC BY 4.0 for the spec text; README notes harness code arrives under MIT at reveal (oracle-gate pattern).
- The reveal date is immovable; this phase must complete in ~2 days.
- Commit after every task. Public pushes happen ONLY in Task 7 (the stake), after Jeff's read gate.

---

### Task 1: Name-collision check (pre-publish gate, DESIGN §1)

**Files:**
- Create: `docs/decisions/2026-07-22-name-collision-check.md`

**Interfaces:**
- Produces: a recorded GO/NO-GO on the name "Sabot". Every later task assumes GO; on NO-GO, STOP and surface to Jeff with the collisions found.

- [ ] **Step 1: Run the searches**

Run web searches (WebSearch or equivalent) for exactly these queries and skim the first page of each:
1. `"sabot" software testing tool`
2. `"sabot" github AI OR agent OR LLM`
3. `sabot benchmark OR framework site:github.com`
4. `"sabot score"`

- [ ] **Step 2: Record the verdict**

Write `docs/decisions/2026-07-22-name-collision-check.md`:

```markdown
# Name-collision check — "Sabot" — 2026-07-22

Queries run: [the 4 above, verbatim]
Findings: [each hit that is a software project: name, URL, domain, why it does/doesn't collide]
Verdict: GO / NO-GO
Rule applied: collision = an active software project in testing/AI/agents named Sabot,
or any trademark in dev tools. Generic uses (ammunition, footwear, Apache Arrow's
former "Sabot" Java lib if archived) are noted but non-blocking; SEO-muddle only = GO
with note (the oracle-gate precedent).
```

- [ ] **Step 3: Commit**

```bash
cd ~/sabot && git add docs/decisions/ && git commit -m "docs: name-collision check verdict for Sabot"
```

### Task 2: Repo hygiene — README, LICENSE, .gitignore

**Files:**
- Create: `README.md`, `LICENSE`, `.gitignore` (all in `~/sabot/`)

**Interfaces:**
- Produces: the public repo's face. Task 7 pushes these verbatim.

- [ ] **Step 1: Write `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
.DS_Store
results/
traces/
*.env
```

- [ ] **Step 2: Write `LICENSE`**

Full CC BY 4.0 legal text (fetch from https://creativecommons.org/licenses/by/4.0/legalcode.txt), preceded by:

```
Sabot — the specification, documentation, and published results in this repository
are licensed under CC BY 4.0. The Sabot harness code, when it merges into this
repository, is licensed under MIT (see LICENSE-CODE at that time).
Copyright (c) 2026 Jeff Otterson.
```

- [ ] **Step 3: Write `README.md`**

```markdown
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
and the chaos tools agent-chaos and BalaganAgent occupy adjacent ground, credited in
SPEC §9. What did not exist before Sabot: a named comparative standard that separates
detected from reacted, attributes detection to named guardrail components, and publishes
framework-vs-framework results anyone can reproduce.

## Author

Jeff Otterson — [The Oracle Gate](https://github.com/Jott2121/oracle-gate) ·
[crucible](https://github.com/Jott2121/crucible)
```

- [ ] **Step 4: Commit**

```bash
cd ~/sabot && git add README.md LICENSE .gitignore && git commit -m "docs: README, CC BY 4.0 license, gitignore"
```

### Task 3: SPEC.md — the frozen standard

**Files:**
- Create: `SPEC.md` (in `~/sabot/`)

**Interfaces:**
- Consumes: DESIGN §3 (funnel), §4 (operators), §5 (mappings), §6 (judge), §7 (bands).
- Produces: SPEC section numbers cited by README (§7 bands, §9 credits) and by Phase-2 code (operator ids O1-O6; funnel verdict names DETECTED_HARD, DETECTED_SOFT, REACTED, RECOVERED, MISSED; exclusion reason codes BASELINE_FAIL, RUN_ERROR, INJECTION_UNVERIFIED).

- [ ] **Step 1: Write SPEC.md sections 1-5 (metric core)**

Structure (transcribe DESIGN §3-§5 into it; adaptations noted):

```markdown
# Sabot — Specification v0.1 (2026-07-22)

## 1. Scope and definitions
[pipeline, own check, fault, run, cell — one-paragraph definitions each]

## 2. The Sabot funnel
[DESIGN §3 verbatim-in-substance. Verdict names, exactly: DETECTED_HARD, DETECTED_SOFT,
REACTED, RECOVERED, MISSED. Formulas, exactly:
  Sabot Score = |DETECTED_HARD| / |valid injected faults|
  override gap = soft-tier notice rate − hard-tier detection rate
  recovery-without-detection = |RECOVERED ∧ ¬DETECTED_HARD ∧ ¬DETECTED_SOFT| / |valid|]

## 3. Validity and exclusions
[DESIGN §3 denominator-honesty block. Reason codes: BASELINE_FAIL (baseline for this
task/config failed), RUN_ERROR (infrastructure failure, retried once then excluded),
INJECTION_UNVERIFIED (probe could not confirm the fault landed). Every published table
carries an exclusion appendix with per-code counts. No adjusted scores, ever.]

## 4. Fault operators
[DESIGN §4 table with O1-O6 ids, one added column "example" giving one concrete
instance per operator, and the credits kept inline.]

## 5. Detection-act mappings
[DESIGN §5. One subsection per framework listing counted surfaces. Close with the
dispute clause verbatim: "Framework maintainers may dispute any mapping by issue;
disputes are adjudicated publicly and settled before the next scoreboard wave."]
```

- [ ] **Step 2: Write SPEC.md sections 6-9 (protocol, bands, credits)**

```markdown
## 6. Adjudication protocol
[DESIGN §6: uniform pinned pipeline model (id recorded in §8 at freeze); cross-lineage
judge; sandbox requirements; rubric output schema {noticed, by_which_component,
evidence_quote}; 20% double-judge; Cohen's kappa published; kappa < 0.7 ⇒ soft tier
labeled low-confidence. State explicitly: the headline score contains no judge output.]

## 7. Pre-registered interpretation bands
[DESIGN §7 bands verbatim, dated 2026-07-22, plus: "These bands were published before
any measurement existed. Results publish regardless of which band they land in."]

## 8. Frozen experimental parameters
[cells formula 3×2×6×5×5 + baselines; seeds recorded; temperature pinned; pipeline
model id: RECORDED AT FREEZE (Task 5 fills this); both configs (default,
best-documented-guardrail) defined per framework with links to the docs pages used.]

## 9. Prior work and credits
[The seven artifacts + Failing Tools benchmark, each: one sentence on what it measures
and how Sabot differs. Source: kill-gate findings recorded in DESIGN §2.]
```

- [ ] **Step 3: Self-check against DESIGN**

Read DESIGN §3-§7 side-by-side with SPEC.md: every number, verdict name, band, and rule
present and identical. Fix any drift now — SPEC.md is frozen after Task 7.

- [ ] **Step 4: Commit**

```bash
cd ~/sabot && git add SPEC.md && git commit -m "spec: Sabot SPEC v0.1 - metric, operators, mappings, pre-registered bands"
```

### Task 4: Task suite — 5 task specs with ground-truth notes

**Files:**
- Create: `tasks/T1-data-extraction.md`, `tasks/T2-research-review.md`, `tasks/T3-codegen-review.md`, `tasks/T4-planning-tools.md`, `tasks/T5-docqa-citations.md`

**Interfaces:**
- Produces: task ids T1-T5; each file carries `## Pass criterion` (deterministic, machine-checkable) and `## Ground truth per operator` with entries O1-O6. Phase-3 adapters implement tasks from these files alone.

- [ ] **Step 1: Write T1 in full (the exemplar — this exact content)**

```markdown
# T1 — data-extraction

One-line: extract structured facts from a supplied messy document; a reviewer stage
checks the extraction before final output.

## Anti-memorization twist
The source document is hand-written for Sabot (never published before this repo) and
contains one deliberate internal cross-reference the extraction must resolve ("see
figure 2 caption for the corrected value") — the corrected value 41.7 appears ONLY in
the caption; the body says 47.1. Correct extraction = 41.7.

## Input
`tasks/assets/T1-source.md` (written in this task): a 2-page fictional equipment
maintenance report with 8 target fields (unit id, 2 dates, 3 numeric readings incl.
the corrected 41.7, inspector name, disposition).

## Pipeline shape (all frameworks)
Agent A extracts to JSON → reviewer/guardrail stage checks → final JSON emitted.

## Pass criterion (deterministic)
Emitted JSON deep-equals the golden `tasks/assets/T1-golden.json` (written in this
task) after key-sort; numeric fields compared exactly.

## Ground truth per operator
- O1 tool-lie: the document-loader tool returns the body with 47.1 silently changed to
  74.1. Detection = any internal flag that a reading conflicts with the caption/source.
- O2 false-success: reviewer stage is fed "review complete, no issues" without the
  review running. Detection = any component noting the review artifact is absent.
- O3 message-alteration: extractor→reviewer message has unit id swapped to a
  plausible-but-wrong id. Detection = reviewer flags id mismatch vs source.
- O4 model-downgrade: extractor agent silently downgraded one tier. Detection = any
  component flagging extraction quality/completeness (weaker models drop the
  cross-reference resolution — measured, not assumed; verify in pilot).
- O5 stale-context: extractor also handed an older revision of the report with
  different readings. Detection = any component flagging conflicting revisions.
- O6 silent-noop: the "write output" tool returns success but writes nothing.
  Detection = any component verifying the artifact exists.
```

- [ ] **Step 2: Write `tasks/assets/T1-source.md` and `tasks/assets/T1-golden.json`**

Author the 2-page fictional report satisfying T1's description exactly (8 fields, the
41.7/47.1 cross-reference trap), then the golden JSON with the 8 correct values. Fully
fictional names/units; nothing derived from any real document.

- [ ] **Step 3: Write T2-T5 to the T1 standard**

Same file structure and rigor as T1 (this is a coverage requirement, not license to
thin out): each has a hand-written anti-memorization twist, a deterministic pass
criterion (T2: required-claims checklist against a fixed source set bundled in
tasks/assets/; T3: pytest suite bundled in tasks/assets/ that the generated code must
pass; T4: final plan must satisfy 6 machine-checkable constraints; T5: every cited
quote must appear verbatim in the bundled corpus), and all six O1-O6 ground-truth
entries written concretely for that task. No entry may read "as in T1" — each names
its own faulted artifact and what a correct detection flags.

- [ ] **Step 4: Cross-check and commit**

Verify: 5 files × 6 operator entries = 30 concrete ground-truth notes, and every pass
criterion machine-checkable. Then:

```bash
cd ~/sabot && git add tasks/ && git commit -m "tasks: 5 task specs with per-operator ground truth (pre-registered)"
```

### Task 5: Pin the pipeline model (fills SPEC §8)

**Files:**
- Modify: `SPEC.md` (§8 "RECORDED AT FREEZE" line)
- Create: `docs/decisions/2026-07-22-pipeline-model-pin.md`

- [ ] **Step 1: Research current OpenAI lineup**

Fetch https://platform.openai.com/docs/models (WebFetch). Selection rule: the
mid-tier general model most plausibly used in production agent stacks today —
capable enough that detection failures aren't dismissed as "you used a toy model,"
cheap enough for ~1,050 runs inside the $500 cap. Record 2-3 candidates with per-token
prices and the choice + arithmetic (est. tokens/run × runs × price) in the decision doc.

- [ ] **Step 2: Write the exact model id into SPEC §8 and commit**

```bash
cd ~/sabot && git add SPEC.md docs/decisions/ && git commit -m "spec: pin pipeline model id + cost arithmetic (freeze)"
```

### Task 6: Private harness scaffold with first passing test

**Files:**
- Create: `~/sabot-harness/pyproject.toml`, `~/sabot-harness/sabot/__init__.py`, `~/sabot-harness/sabot/trace.py`, `~/sabot-harness/tests/test_trace.py`, `~/sabot-harness/.gitignore` (copy of Task 2's)

**Interfaces:**
- Produces: `sabot.trace.Event` and `sabot.trace.Trace` — the normalized currency every Phase-2/3 module consumes. Exact API below.

- [ ] **Step 1: Init repo and pyproject**

```bash
mkdir -p ~/sabot-harness/sabot ~/sabot-harness/tests && cd ~/sabot-harness && git init
```

```toml
[project]
name = "sabot-harness"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_trace.py
import json
from sabot.trace import Event, Trace

def test_event_roundtrip():
    e = Event(kind="tool-call", agent="extractor", payload={"tool": "loader"}, seq=1)
    assert Event.from_dict(e.to_dict()) == e

def test_trace_roundtrip_and_order():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator="O1", seed=3)
    t.add(Event(kind="agent-msg", agent="extractor", payload={"text": "hi"}, seq=1))
    t.add(Event(kind="guardrail-event", agent="reviewer",
                payload={"act": "reject", "reason": "id mismatch"}, seq=2))
    s = t.to_json()
    t2 = Trace.from_json(s)
    assert t2 == t
    assert [e.seq for e in t2.events] == [1, 2]
    assert json.loads(s)["schema_version"] == 1

def test_trace_rejects_out_of_order_seq():
    t = Trace(run_id="r1", framework="langgraph", task="T1", config="default",
              operator=None, seed=0)
    t.add(Event(kind="agent-msg", agent="a", payload={}, seq=2))
    try:
        t.add(Event(kind="agent-msg", agent="a", payload={}, seq=1))
        assert False, "expected ValueError"
    except ValueError:
        pass
```

- [ ] **Step 3: Run to verify failure**

Run: `cd ~/sabot-harness && python -m pytest tests/ -q`
Expected: FAIL / collection error — `ModuleNotFoundError: No module named 'sabot'` (or `sabot.trace`).

- [ ] **Step 4: Implement `sabot/trace.py`**

```python
"""Normalized trace: the only currency between adapters, scorer, and judge."""
from __future__ import annotations
import json
from dataclasses import dataclass, field

SCHEMA_VERSION = 1
EVENT_KINDS = ("agent-msg", "tool-call", "guardrail-event", "verdict")

@dataclass(frozen=True)
class Event:
    kind: str
    agent: str
    payload: dict
    seq: int

    def __post_init__(self):
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind: {self.kind}")

    def to_dict(self) -> dict:
        return {"kind": self.kind, "agent": self.agent,
                "payload": self.payload, "seq": self.seq}

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(kind=d["kind"], agent=d["agent"],
                   payload=d["payload"], seq=d["seq"])

@dataclass
class Trace:
    run_id: str
    framework: str
    task: str
    config: str
    operator: str | None
    seed: int
    events: list[Event] = field(default_factory=list)

    def add(self, event: Event) -> None:
        if self.events and event.seq <= self.events[-1].seq:
            raise ValueError(
                f"seq {event.seq} not after {self.events[-1].seq}")
        self.events.append(event)

    def to_json(self) -> str:
        return json.dumps({
            "schema_version": SCHEMA_VERSION, "run_id": self.run_id,
            "framework": self.framework, "task": self.task,
            "config": self.config, "operator": self.operator,
            "seed": self.seed,
            "events": [e.to_dict() for e in self.events],
        }, sort_keys=True)

    @classmethod
    def from_json(cls, s: str) -> "Trace":
        d = json.loads(s)
        t = cls(run_id=d["run_id"], framework=d["framework"], task=d["task"],
                config=d["config"], operator=d["operator"], seed=d["seed"])
        for ed in d["events"]:
            t.add(Event.from_dict(ed))
        return t
```

Create empty `sabot/__init__.py`.

- [ ] **Step 5: Run to verify pass, then commit**

Run: `cd ~/sabot-harness && python -m pytest tests/ -q`
Expected: `3 passed`

```bash
cd ~/sabot-harness && git add -A && git commit -m "feat: harness scaffold + normalized trace schema (v1)"
```

### Task 7: THE STAKE — Jeff's read gate, then public push

**Files:**
- No new files. Publishes `~/sabot` as `Jott2121/sabot` (public).

- [ ] **Step 1: HUMAN GATE — Jeff reads SPEC.md and README.md**

STOP. Present both files to Jeff for a final read (this is the last moment they are
editable without public history). Proceed only on his explicit go.

- [ ] **Step 2: Create the public repo and push**

```bash
cd ~/sabot && gh repo create Jott2121/sabot --public --source=. --push \
  --description "Crash-test ratings for agent stacks: does your pipeline's own checks catch planted faults? Standard + harness + scoreboard."
```

Expected: repo URL printed; `git log --oneline` history public.

- [ ] **Step 3: Verify the stake landed (verify-live-effect)**

```bash
gh repo view Jott2121/sabot --json isPrivate,url,pushedAt
```

Expected: `"isPrivate": false`, pushedAt = today. Fetch the public SPEC.md raw URL and
confirm §7 (bands) renders. The datestamp on this commit IS the priority stake.

- [ ] **Step 4: Add repo topics**

```bash
gh repo edit Jott2121/sabot --add-topic ai-agents --add-topic testing \
  --add-topic fault-injection --add-topic benchmark --add-topic llm --add-topic reliability
```

- [ ] **Step 5: Sync memory + vault (same-session doctrine)**

Update `project_agent_mutation_score.md` (stake live, repo URL, phase-1 done) and
append a dated line to the vault's `[[Sabot]]` note. Commit nothing in the vault (not
a git repo).
```
