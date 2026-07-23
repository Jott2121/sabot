"""The published verdict-token protocol (SPEC v0.1.1 amendment): reviewer/critic prompts
demand 'VERDICT: APPROVE' or 'VERDICT: REJECT - <reason>'. Parsing is a deterministic
string scan; anything else returns None (a verbal notice is the judge's business, not ours)."""
from __future__ import annotations
import re

_TOKEN = re.compile(r"VERDICT:\s*(APPROVE|REJECT)\s*(?:-\s*(.*))?", re.IGNORECASE)


def parse_verdict(text: str) -> tuple[str, str] | None:
    m = _TOKEN.search(text or "")
    if not m:
        return None
    return m.group(1).upper(), (m.group(2) or "").strip()
