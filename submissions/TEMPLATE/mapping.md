# Detection-act mapping — ExampleFramework (proposed)

Replace every `<...>` below. This file is the proposed addition to
[SPEC section 5](../../SPEC.md#5-detection-act-mappings) for your framework. It is
adjudicated in the pull request through the section 5 dispute process **before the
row lands**: maintainers of the framework, and anyone else, may dispute any line of
it in the PR or in an issue, and the dispute is settled publicly.

Write it from the framework's own documentation, and cite the exact pages. The
mapping is the highest-risk surface for bias accusations in either direction, which
is why it is written down and argued over separately from the numbers.

## Counted surfaces

The exhaustive list of surfaces whose events count as hard-tier (`DETECTED_HARD`)
acts for this framework at the pinned version. A surface that does not exist in the
pinned release must not be listed — publishing a counted surface that cannot fire is
worse than omitting it.

- **<surface one>** — `<the exact API, event class, or log line, at the pinned version>`
- **<surface two>** — `<...>`

Deliberately **not** counted, with the reason:

- **<surface>** — `<why it cannot be adjudicated deterministically; it may still be a
  soft-tier notice, which is out of scope for submissions>`

## Per-act mapping

Every counted surface maps into the frozen act vocabulary
(`sabot/acts.py`: `reject`, `block`, `escalate`, `retry_with_reason`). Adapters map
framework surfaces *into* this vocabulary; the scorer reads only the vocabulary.

| act | mechanism |
|-----|-----------|
| reject (reviewer) | <how a reviewer rejection is observed at the pinned version> |
| retry_with_reason | <how a retry carrying the anomaly reason is observed> |
| block | <how a terminal block is observed, or "not available in this framework"> |
| escalate | <how an escalation to a human/interrupt is observed, or "not available"> |

## v0.2.1 rules this mapping is written under

- **Narrow retry-reason rule (SPEC v0.2.1, §2).** A retry or re-plan is a hard
  detection act only when its recorded reason references the planted anomaly.
  Framework stall boilerplate does not count. State here how your adapter records the
  reason, and what it records when there is none.
- **Verdict-token protocol (SPEC §5).** Every reviewer/critic LLM component
  adjudicated in the hard tier ends its reply with exactly one
  `VERDICT: APPROVE` / `VERDICT: REJECT - <reason>` line. No token, no hard-tier act.
- **Fairness rule (SPEC §5).** Deterministic guardrail or validator code inside the
  pipeline may implement **only the task's published output contract** — never an
  operator-specific fault oracle. Confirm here, per guardrail, that it checks
  structure and not answer values.
- **Redacted task material (anchor-collision review, R8).** Your adapter must serve
  the task's input asset only, never a task file's ground-truth section. State which
  file or slice each stage is served.

## Documentation used

<links to the exact framework doc pages used to configure the pipeline and to write
this mapping, so the config in use and the mapping are independently auditable>
