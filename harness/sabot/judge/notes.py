"""Per-(task, operator) ground-truth notes for the judge rubric (SPEC section 6), parsed
from the PUBLIC task files' '## Ground truth per operator' sections — the pre-registered
single source of truth (same posture as checks.py: nothing vendored, nothing invented).
PURE: path in, string out; no defaults, no guessing — a missing note is a KeyError."""
from __future__ import annotations
import re
from pathlib import Path

_SECTION = "## Ground truth per operator"
_BULLET = re.compile(r"^- (O[0-9]+) ", re.MULTILINE)
_WS = re.compile(r"\s+")


def ground_truth_note(task_id: str, operator_id: str, tasks_dir: Path) -> str:
    matches = sorted(Path(tasks_dir).glob(f"{task_id}-*.md"))
    if not matches:
        raise KeyError(f"no task file for {task_id!r} in {tasks_dir}")
    text = matches[0].read_text()
    if _SECTION not in text:
        raise KeyError(f"{matches[0].name} has no {_SECTION!r} section")
    section = text.split(_SECTION, 1)[1]
    next_heading = re.search(r"^## ", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]
    bullets: dict[str, str] = {}
    parts = _BULLET.split(section)
    # parts = [preamble, "O1", body1, "O2", body2, ...]
    for op, body in zip(parts[1::2], parts[2::2]):
        bullets[op] = _WS.sub(" ", body).strip()
    if operator_id not in bullets:
        raise KeyError(f"{task_id}: no ground-truth bullet for {operator_id!r}")
    return f"{operator_id} {bullets[operator_id]}"
