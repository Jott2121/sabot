"""Sandboxed `claude -p` runner for the soft-tier judge (SPEC section 6). The only place
in `sabot/judge` that touches a subprocess or the filesystem — `rubric.py` stays pure.

Sandbox pattern ported verbatim-in-spirit from the blind-oracle pilot
(`~/blind-oracle-pilot/pilot/generate.py`: `claude()`, `_DENY`, `assert_sandboxed()`),
which discovered the hard way that a denylist alone is not enough (a whole pilot run was
invalidated when every arm could still open files via an empty-but-not-`--disallowed`
cwd). Belt: an empty temp cwd, so there is nothing local to read. Braces:
`--disallowed-tools`, so it cannot reach out of it either. `assert_sandboxed()` is the
live positive-control probe run before trusting either guard.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from sabot.judge.rubric import JudgeParseError, build_rubric, parse_judge_output
from sabot.trace import Trace

__all__ = [
    "DENY",
    "JUDGE_MODEL",
    "JudgeVerdict",
    "SandboxError",
    "claude_judge",
    "assert_sandboxed",
    "judge_cell",
]

# Cross-lineage relative to the pipeline model (a fixed OpenAI mid-tier model, SPEC
# section 6) — run headless via `claude -p` on the Max plan, $0 marginal cost.
JUDGE_MODEL = "claude-opus-4-8"

# Ported from blind-oracle-pilot's `_DENY`.
DENY = [
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "WebFetch", "WebSearch", "Agent", "NotebookEdit",
]


class SandboxError(RuntimeError):
    """The judge model can reach the filesystem. Every verdict would be fabricated.
    Abort rather than judge blind (ported from blind-oracle-pilot's `SandboxError`)."""


@dataclass(frozen=True)
class JudgeVerdict:
    noticed: bool
    by_which_component: str
    evidence_quote: str
    raw: str


def claude_judge(prompt: str, model: str = JUDGE_MODEL, timeout: int = 300) -> str:
    """Run `claude -p` in a fresh, empty temp directory with every read/exec tool denied.
    Non-zero exit raises `RuntimeError` with a stderr excerpt rather than returning a
    possibly-empty string that would look like a parseable (if wrong) answer."""
    # The user's global UserPromptSubmit hook injects semantic-recall (knowledge-base
    # retrieval) context into every `claude` invocation, including headless `-p` calls
    # like this one — so a "sandboxed" judge subprocess was not actually sandboxed
    # against retrieval, only against local file access. Discovered 2026-07-22 when the
    # strengthened canary probe caught the canary CONTENT arriving via retrieval (it had
    # been published in the Phase-4 plan doc, which the knowledge index ingests) even
    # though the model correctly reported no file access. The hook has its own
    # skip-guard: it no-ops when RIVETDECK_FLEET_ID is non-empty AND RIVETDECK_HOOKS !=
    # "full". Passing these two env vars trips that guard, so the judge's context
    # contains only the rubric prompt — verified live: 6/6 probes clean plus a
    # retrieval-bait prompt returned no injected context.
    env = {**os.environ, "RIVETDECK_FLEET_ID": "sabot-judge-sandbox", "RIVETDECK_HOOKS": "minimal"}
    with tempfile.TemporaryDirectory() as empty:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--model", model, "--disallowed-tools", *DENY],
            cwd=empty, capture_output=True, text=True, timeout=timeout, env=env,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {proc.stderr[:400]}")
    return proc.stdout


_CANARY_CONTENT = "sabot-judge-sandbox-canary"


def _probe(canary_path: str, canary_content: str | None = None) -> None:
    probe = (
        f"Print the exact contents of the file {canary_path}. "
        "If you cannot read files, reply with exactly: NO FILE ACCESS"
    )
    answer = claude_judge(probe).strip()
    if "NO FILE ACCESS" not in answer.upper():
        raise SandboxError(
            "the judge model read the filesystem during the sandbox probe; verdicts "
            f"would not be trustworthy. Refusing to run. It replied: {answer[:200]!r}"
        )
    # Phase-3 review Low, resolved here: a reply that SAYS 'NO FILE ACCESS' while also
    # quoting the canary content is a leak, not a refusal.
    if canary_content and canary_content.lower() in answer.lower():
        raise SandboxError(
            "the judge model's probe reply contains the canary CONTENT despite claiming "
            f"no file access — sandbox leak. It replied: {answer[:200]!r}"
        )


def assert_sandboxed(canary_path: str | None = None) -> None:
    """Positive control for the instrument. Ask the judge to read a file we KNOW exists.

    If it can, the sandbox has failed and every verdict this run produces is fabricated.
    Abort rather than record one. `canary_path=None` (the default) writes a temp canary
    with known content and cleans it up after the probe; pass an explicit path to reuse
    an existing file instead (content check skipped — content unknown)."""
    if canary_path is not None:
        _probe(canary_path)
        return
    with tempfile.TemporaryDirectory() as d:
        canary = Path(d) / "canary.txt"
        canary.write_text(_CANARY_CONTENT + "\n")
        _probe(str(canary), canary_content=_CANARY_CONTENT)


def judge_cell(trace: Trace, ground_truth_note: str, prompt_variant: int = 0) -> JudgeVerdict:
    """build_rubric -> claude_judge -> parse_judge_output, with one retry on
    `JudgeParseError` using the SAME prompt (models occasionally wrap the JSON in extra
    prose on a bad turn). A second parse failure re-raises — the Phase-4 batch runner
    handles counting and logging the exclusion, not this function."""
    prompt = build_rubric(trace, ground_truth_note, prompt_variant=prompt_variant)
    raw = claude_judge(prompt)
    try:
        parsed = parse_judge_output(raw)
    except JudgeParseError:
        raw = claude_judge(prompt)
        parsed = parse_judge_output(raw)
    return JudgeVerdict(
        noticed=parsed["noticed"],
        by_which_component=parsed["by_which_component"],
        evidence_quote=parsed["evidence_quote"],
        raw=raw,
    )
