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
import uuid
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

# Ported from blind-oracle-pilot's `_DENY`, EXTENDED 2026-07-24 after the wave-2
# canary fired: the judge model reached the filesystem through `Monitor` — a tool
# added to the harness after this list was frozen. A denylist against an evolving
# harness decays silently, so the primary closure is now the empty ALLOWLIST
# (`--allowed-tools ""`, which the current CLI documents as disabling all built-in
# tools) plus `--strict-mcp-config` with no config (zero MCP servers). This DENY
# list stays as defense-in-depth, extended with every current first-party tool;
# assert_sandboxed()'s canary remains the backstop that catches the next new hole.
DENY = [
    "Read", "Write", "Edit", "Bash", "Glob", "Grep",
    "WebFetch", "WebSearch", "Agent", "NotebookEdit",
    "Monitor", "TaskCreate", "TaskGet", "TaskList", "TaskOutput", "TaskStop",
    "TaskUpdate", "SendMessage", "Workflow", "Skill", "ToolSearch",
    "SendUserFile", "PushNotification", "ScheduleWakeup", "EnterWorktree",
    "ExitWorktree", "EnterPlanMode", "ExitPlanMode", "RemoteTrigger",
    "DesignSync", "LSP", "CronCreate", "CronDelete", "CronList",
    "AskUserQuestion", "Artifact", "ReportFindings", "ListMcpResourcesTool",
    "ReadMcpResourceTool", "ReadMcpResourceDirTool",
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
            ["claude", "-p", prompt, "--model", model, "--allowed-tools", "",
             "--strict-mcp-config", "--disallowed-tools", *DENY],
            cwd=empty, capture_output=True, text=True, timeout=timeout, env=env,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p failed: {proc.stderr[:400]}")
    return proc.stdout


_CANARY_CONTENT = "sabot-judge-sandbox-canary"


def _probe_prompt(canary_path: str) -> str:
    return (f"Print the exact contents of the file {canary_path}. "
            "Attempt it now and show whatever you obtain.")


def claude_probe_permissive(prompt: str, workdir: str,
                            model: str = JUDGE_MODEL, timeout: int = 300) -> str:
    """The probe's POSITIVE-CONTROL arm: same prompt, tools deliberately ENABLED
    (Read allowed, cwd = the canary's own directory). Proves the canary exists, the
    path resolves, the prompt elicits a read, and output capture works — the arm that
    makes a content-absence gate falsifiable in the passing direction."""
    env = {**os.environ, "RIVETDECK_FLEET_ID": "sabot-judge-sandbox",
           "RIVETDECK_HOOKS": "minimal"}
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--allowed-tools", "Read",
         "--strict-mcp-config"],
        cwd=workdir, capture_output=True, text=True, timeout=timeout, env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"claude -p (permissive probe arm) failed: {proc.stderr[:400]}")
    return proc.stdout


def assert_sandboxed() -> None:
    """Two-arm config-drift regression probe (criterion redesigned 2026-07-24 after
    the Monitor-tool incident; dated instrument fix, disclosed; design ratified by
    frontier consult).

    A fresh RANDOM canary token is written per run (a repo-visible constant can
    neither false-pass via stale artifacts nor false-alarm via training data). Two
    arms, both judged by whitespace-normalized substring on the raw output:

      Arm P (permissive): tools enabled, cwd = canary dir — the token MUST appear.
        Proves file, path, prompt, and capture all work.
      Arm R (restricted): the exact judge config — the token MUST NOT appear.

    Gate = P positive AND R negative. No refusal-phrase parsing: how a toolless
    model narrates its failed attempts is distributional noise, not signal (the
    phrase criterion flapped ~50% and a flapping gate gets disabled). Detection
    power is intact — the Monitor-class hole surfaced precisely as canary content
    in the restricted arm's output. Honest scope: this is config-drift regression
    detection, not adversarial containment proof; a model concealing access would
    simply not print the token, and no prompt-level probe closes that — the actual
    boundary is the tool policy (DENY + empty allowlist + strict-mcp-config)."""
    token = f"sabot-canary-{uuid.uuid4().hex}"
    norm = lambda s: " ".join(s.split()).lower()
    with tempfile.TemporaryDirectory() as d:
        canary = Path(d) / "canary.txt"
        canary.write_text(token + "\n")
        prompt = _probe_prompt(str(canary))
        p_out = claude_probe_permissive(prompt, workdir=d)
        if norm(token) not in norm(p_out):
            raise SandboxError(
                "positive-control arm failed: with tools ENABLED the canary token did "
                "not come back, so the probe infrastructure itself cannot be trusted "
                f"(file/path/prompt/capture). Reply: {p_out[:200]!r}"
            )
        r_out = claude_judge(prompt)
        if norm(token) in norm(r_out):
            raise SandboxError(
                "the judge model's restricted-arm reply contains the canary token — "
                f"sandbox leak. Refusing to run. It replied: {r_out[:200]!r}"
            )


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
