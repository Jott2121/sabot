"""Wave-2 anomaly-first probe adapter — CrewAI. The ONLY change from the frozen wave-1
adapter is the reviewer system prompt: each _T?_REVIEWER_SYS gains the ANOMALY-FIRST
addendum demanding a FLAGS line before the verdict. The verdict-token parse is
position-independent, so every wave-1 surface (acts, guardrails, scoring) is untouched;
the FLAGS text lands in the trace via the existing reviewer events and is adjudicated
post-hoc by sabot.probe.scan_trace_flags. T4 is outside the probe scope and keeps the
wave-1 prompt."""
from __future__ import annotations
from sabot.adapters.crewai_adapter import CrewAIAdapter
from sabot.probe import CREWAI_ADDENDUM


class ProbeCrewAIAdapter(CrewAIAdapter):
    _T1_REVIEWER_SYS = CrewAIAdapter._T1_REVIEWER_SYS + CREWAI_ADDENDUM
    _T2_REVIEWER_SYS = CrewAIAdapter._T2_REVIEWER_SYS + CREWAI_ADDENDUM
    _T3_REVIEWER_SYS = CrewAIAdapter._T3_REVIEWER_SYS + CREWAI_ADDENDUM
    _T5_REVIEWER_SYS = CrewAIAdapter._T5_REVIEWER_SYS + CREWAI_ADDENDUM
