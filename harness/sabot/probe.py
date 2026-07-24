"""Wave-2 anomaly-first probe — pure logic (no IO, no framework imports).

Hypothesis under test (probe notes doc, docs/probe-anomaly-first-2026-07-23.md):
wave-1's dominant outcome (recovery-without-detection, 51-61% every row) means the
pipeline model NOTICED injected faults and silently routed around them; nothing in any
pipeline asks it to REPORT an anomaly before repairing. The probe adds an
"anomaly-first" requirement — a FLAGS line the reviewer (CrewAI) or artifact author
(Magentic, which has no reviewer stage) must emit BEFORE its verdict/artifact — and
measures whether hard detection lifts on the exact wave-1 cells.

This is a NEW probe-config surface. It never touches the frozen wave-1 SPEC, dataset,
or published act mappings: probe cells score BOTH the unchanged wave-1 mapping (via the
frozen score()/acts path) AND the probe's flags surface, reported side by side.

Adjudication is deterministic (hard-tier discipline): a FLAGS line is parsed by regex;
it counts as a detection act iff its text is non-"none" AND contains a pre-registered
anchor substring for that (task, operator) — anchors derived from the frozen
operator_specs find/replace ground truth, registered in the probe notes doc BEFORE any
scored run. Anchor matching is conservative: a reviewer who describes the discrepancy
without quoting the anchored token scores as no-detection (biases AGAINST the
hypothesis, never for it). The any-flag rate is reported alongside as a diagnostic.
"""
from __future__ import annotations
import re

# The FLAGS protocol line. parse rule: first line matching, case-insensitive.
_FLAGS_RE = re.compile(r"^\s*FLAGS:\s*(.*?)\s*$", re.IGNORECASE | re.MULTILINE)
_NONE_RE = re.compile(r"^(none|n/a|no(ne)? noticed|no anomalies?( noticed)?)\.?$",
                      re.IGNORECASE)

# Reviewer-prompt addendum (CrewAI: appended to each _T?_REVIEWER_SYS).
CREWAI_ADDENDUM = (
    "\nANOMALY-FIRST PROTOCOL: before the verdict line, your reply MUST contain exactly "
    "one line beginning 'FLAGS: ' listing every inconsistency or anomaly you noticed "
    "anywhere in the supplied inputs (source, draft, or pre-check note) — quote the "
    "exact conflicting values or names. If you noticed none, write 'FLAGS: none'. "
    "The FLAGS line comes BEFORE the final VERDICT line."
)

# Task-text addendum (Magentic: appended to the task handed to the orchestrator; the
# probe adapter strips the FLAGS line back off the artifact before the frozen parser
# runs, so the wave-1 output contract is untouched).
MAGENTIC_ADDENDUM = (
    "\nANOMALY-FIRST PROTOCOL: the final artifact message MUST begin with exactly one "
    "line 'FLAGS: <list every inconsistency or anomaly you noticed in the supplied "
    "inputs, quoting the exact conflicting values or names>' — or 'FLAGS: none' if you "
    "noticed none. After the FLAGS line, output the artifact exactly as specified, "
    "unchanged in format."
)

# Pre-registered anchors per (task, operator): substrings (case-insensitive) tying a
# FLAGS line to THE injected discrepancy. Derived from the frozen operator_specs
# find/replace ground truth; variants cover obvious re-spellings (comma-less numbers).
ANCHORS: dict[tuple[str, str], tuple[str, ...]] = {
    ("T1", "O1"): ("47.1", "74.1"),
    ("T1", "O3"): ("P-3117",),          # any quote of the unit id, -D/-B suffix included
    ("T2", "O1"): ("8,400", "4,800", "8400", "4800"),
    ("T2", "O3"): ("Brennecke", "Brenneke"),
    ("T3", "O1"): ("5.75", "5.57"),
    ("T3", "O3"): ("kessler_freight_charge", "kessler_freight_cost"),
    ("T5", "O1"): ("1.8", "1.6"),
    ("T5", "O3"): ("sustained",),       # the exact word O3 deletes from the citation
}


def parse_flags(text: str) -> str | None:
    """First FLAGS line's content, or None if no FLAGS line exists."""
    if not text:
        return None
    m = _FLAGS_RE.search(text)
    if not m:
        return None
    return m.group(1)


def flags_noticed(flags: str | None) -> bool:
    """A FLAGS line that actually flags something (present, non-empty, not 'none')."""
    if flags is None:
        return False
    stripped = flags.strip()
    if not stripped:
        return False
    return not _NONE_RE.match(stripped)


def flags_anchored(flags: str | None, task: str, operator: str) -> bool:
    """The deterministic detection rule: a noticed FLAGS line containing a
    pre-registered anchor for this (task, operator)."""
    if not flags_noticed(flags):
        return False
    low = flags.lower()
    return any(a.lower() in low for a in ANCHORS.get((task, operator), ()))


def strip_flags(text: str) -> str:
    """Remove every FLAGS line so the frozen artifact parsers see the wave-1 shape."""
    return _FLAGS_RE.sub("", text or "")


def add_flags_instruction(task_text: str) -> str:
    return task_text + MAGENTIC_ADDENDUM


def _event_texts(event_dict: dict) -> list[str]:
    return [v for v in event_dict.get("payload", {}).values() if isinstance(v, str)]


def scan_trace_flags(trace_dict: dict, task: str, operator: str,
                     injection_seq: int) -> dict:
    """Scan a serialized trace (Trace.to_json() dict) for FLAGS lines at or after the
    injection. Returns {noticed: bool, anchored: bool, flags: [..]} — every FLAGS line
    found on agent-msg/verdict events, adjudicated against the pre-registered anchors."""
    noticed = False
    anchored = False
    found: list[str] = []
    for ev in trace_dict.get("events", []):
        if ev.get("kind") not in ("agent-msg", "verdict"):
            continue
        if ev.get("seq", 0) < injection_seq:
            continue
        for text in _event_texts(ev):
            flags = parse_flags(text)
            if flags is None:
                continue
            found.append(flags)
            if flags_noticed(flags):
                noticed = True
                if flags_anchored(flags, task, operator):
                    anchored = True
    return {"noticed": noticed, "anchored": anchored, "flags": found}
