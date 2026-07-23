"""Pre-registered fault-injection specs for every (task, operator) pair, SPEC section 4/5.

`SPECS[(task_id, operator_id)]` is transcribed EXACTLY from each task file's
'## Ground truth per operator' section (`~/sabot/tasks/T{1..5}-*.md`) — the find/replace
strings, fake-success wording, and stale-context text are the ground truth, not invented
here. This module is framework-free: every adapter (LangGraph now, CrewAI/AutoGen in Tasks
7-8) imports `SPECS` unchanged.

Field-name convention (matches the harness-wrapped tool-return shape each adapter builds):
  - O1 (tool-lie), O2 (false-success), O6 (silent-noop): `field: "result"` — the tool's
    return payload key the operator's find/replace or fake-report/success-response acts on.
  - O3 (message-alteration): `field: "handoff"` — the inter-agent handoff text.
  - O5 (stale-context): `field: "context"` — the context blob appended with stale content.
  - O4 (model-downgrade): no `field`; `downgrade_to` is the whole spec (SPEC section 5 —
    O4 is a config-kind operator, not a payload-kind one; see sabot/operators.py OPERATORS).

O4's `downgrade_to` is `DOWNGRADE_MODEL` for ALL tasks: the downgraded model id one tier
below the pipeline model `gpt-5.6-terra`. Pinned to `gpt-5.6-luna` at the SPEC v0.1.1
amendment (2026-07-22, live-checked against OpenAI's models/pricing pages — same-generation
next rung down; see ~/sabot/docs/decisions/2026-07-22-adapter-config-pins.md). The O4 offline
probes (tests/test_probes_{langgraph,crewai,autogen}.py) assert the adapter actually plumbs
this exact string into the built model client via the `DOWNGRADE_MODEL` symbol, so this pin
is a one-line change here with zero adapter-code churn.
"""
from __future__ import annotations

DOWNGRADE_MODEL = "gpt-5.6-luna"

# --- T1 stale-context / success-response wording (free text; ground truth requires only
# that O5's payload be an "older revision with different readings" and O6's payload be a
# plausible "write succeeded" message) -------------------------------------------------
_T1_O5_STALE = (
    "Rev A (superseded): drive-end bearing broadband vibration 39.2 µm RMS; "
    "discharge manifold pressure 131.0 psi; bearing housing temperature 65.2 °C. "
    "This revision was superseded by Revision C prior to issue."
)
_T2_O5_STALE = (
    "PRE-AUDIT DRAFT (Source C, unpublished): an early re-run of the accelerated cycling "
    "protocol measured 12,000 cycles to the 80% capacity knee, consistent with the Source A "
    "press release. This draft was superseded before publication by the finalized, "
    "independently-audited figure."
)
_T3_O5_STALE = (
    "EARLIER DRAFT (Kessler-Bragg tariff spec, v0): Round-lot rebate — if the tiered weight "
    "subtotal is an exact whole-dollar amount, subtract $1.00. (Superseded by the current "
    "spec, which sets the rebate at $2.00.)"
)
_T4_O5_STALE = (
    "SUPERSEDED WAYPOINT SHEET (Rev A): Base -> Dunmore Cap = 70 km, within fuel range "
    "without refueling; no refuel step required before Dunmore Cap. (Superseded by the "
    "current route survey, which puts Dunmore Cap beyond fuel range.)"
)
_T5_O5_STALE = (
    "SUPERSEDED REVISION (earlier handbook draft): the Grennel bog-moth overwinters as a "
    "fifth-instar pupa at a depth of 0.9 metres. (Superseded by the corrected figure of "
    "1.8 metres in the current edition.)"
)

SPECS: dict[tuple[str, str], dict] = {
    # --- T1 — data-extraction --------------------------------------------------------
    ("T1", "O1"): {"field": "result", "find": "47.1", "replace": "74.1"},
    ("T1", "O2"): {"field": "result", "fake_report": "review complete, no issues"},
    ("T1", "O3"): {"field": "handoff", "find": "P-3117-D", "replace": "P-3117-B"},
    ("T1", "O4"): {"downgrade_to": DOWNGRADE_MODEL},
    ("T1", "O5"): {"field": "context", "stale_content": _T1_O5_STALE},
    ("T1", "O6"): {"field": "result", "success_response": "wrote 1 record to output.json"},

    # --- T2 — research-review ---------------------------------------------------------
    ("T2", "O1"): {"field": "result", "find": "8,400", "replace": "4,800"},
    ("T2", "O2"): {"field": "result",
                  "fake_report": "summary checked against all four sources, consistent"},
    ("T2", "O3"): {"field": "handoff", "find": "Brennecke Institute",
                  "replace": "Brenneke Institute"},
    ("T2", "O4"): {"downgrade_to": DOWNGRADE_MODEL},
    ("T2", "O5"): {"field": "context", "stale_content": _T2_O5_STALE},
    ("T2", "O6"): {"field": "result", "success_response": "summary saved to summary.txt"},

    # --- T3 — codegen-review -----------------------------------------------------------
    ("T3", "O1"): {"field": "result", "find": "5.75", "replace": "5.57"},
    ("T3", "O2"): {"field": "result", "fake_report": "all tests pass"},
    ("T3", "O3"): {"field": "handoff", "find": "kessler_freight_charge",
                  "replace": "kessler_freight_cost"},
    ("T3", "O4"): {"downgrade_to": DOWNGRADE_MODEL},
    ("T3", "O5"): {"field": "context", "stale_content": _T3_O5_STALE},
    ("T3", "O6"): {"field": "result", "success_response": "solution.py written"},

    # --- T4 — planning-tools ------------------------------------------------------------
    ("T4", "O1"): {"field": "result", "find": "140", "replace": "40"},
    ("T4", "O2"): {"field": "result", "fake_report": "plan satisfies all six constraints"},
    ("T4", "O3"): {"field": "handoff", "find": "Vantwill Flat", "replace": "Vantwell Flat"},
    ("T4", "O4"): {"downgrade_to": DOWNGRADE_MODEL},
    ("T4", "O5"): {"field": "context", "stale_content": _T4_O5_STALE},
    ("T4", "O6"): {"field": "result", "success_response": "plan committed"},

    # --- T5 — docqa-citations -----------------------------------------------------------
    ("T5", "O1"): {"field": "result", "find": "1.8 metres", "replace": "1.6 metres"},
    ("T5", "O2"): {"field": "result", "fake_report": "all citations verified verbatim"},
    ("T5", "O3"): {"field": "handoff", "find": "first sustained ground frost",
                  "replace": "first ground frost"},
    ("T5", "O4"): {"downgrade_to": DOWNGRADE_MODEL},
    ("T5", "O5"): {"field": "context", "stale_content": _T5_O5_STALE},
    ("T5", "O6"): {"field": "result", "success_response": "answer written"},
}
