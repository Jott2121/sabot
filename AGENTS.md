# AGENTS.md — sabot

> Portable agent instructions. Read by Cursor (local and cloud agents), Codex, and Grok Bot cloud-agent runs.
> There is no `CLAUDE.md`. This file is the source of truth. If a `CLAUDE.md` is added later, make it a pointer here.
> Keep this file under ~150 lines. Procedures live in `.cursor/skills/`. Scoped rules live in `.cursor/rules/*.mdc`. Review rules live in `.cursor/BUGBOT.md`.

## What this repo is

Sabot plants controlled faults inside running multi-agent pipelines (LangGraph, CrewAI, AutoGen/Magentic-One) and scores whether the pipeline's own reviewer and guardrail stages flag them, act on them, or miss them. It is a frozen metric spec (`SPEC.md` v0.2.1), an Apache-2.0 harness, and a public scoreboard. Headline result, recomputed offline from the committed traces: median hard-tier detection **16.7%** (wave 1) to **55.0%** (wave 2) after one anomaly-first reporting change. Reproduce with the `--check` commands below. If a printed number disagrees with the README, the repo is wrong.

- **Status:** active · **License:** spec, docs, and results CC BY 4.0 (`LICENSE`); harness Apache-2.0 (`LICENSE-CODE`) · **Package:** `sabot-harness` (not on PyPI; `harness/pyproject.toml`)
- **Entry points:** `harness/sabot/`, `harness/tests/`, `harness/scripts/`, `SPEC.md`
- **Part of:** the governed-agent stack (rag-guard · graph-guard · agent-gate · crucible · oracle-gate · agent-cost-attribution · bow · fleet-mode)

## Commands (run these, don't guess)

Two version floors. Offline scorers under `harness/scripts/` are **Python 3.9+, standard library only** — no install. The harness itself is **Python 3.11+** plus pinned framework venvs (`harness/scripts/setup_venvs.sh`). Commands below are from `harness/`.

```bash
# tests (Python 3.11+). CI comment: 446 passed, 15 skipped, 2 deselected.
python -m pip install --upgrade pip "pytest>=8" pytest-cov
python -m pytest tests/ -q --ignore=tests/test_venvs.py --cov --cov-report=term-missing --cov-fail-under=90

# receipts. These --check scorers recompute published numbers and compare
# them byte-for-byte to the frozen baselines. Do not add a second checker.
python scripts/score_strict.py --check
python scripts/score_uncertainty.py --check
python scripts/score_by_operator.py --check

# third-party scoreboard rows. submissions/TEMPLATE is a skeleton and is meant to fail.
python scripts/validate_submission.py ../submissions/<row>
```

Lint and typecheck are not configured. Do not add ruff or mypy in a drive-by change.

A task is not done until the pytest command and the three `--check` commands pass and the output is pasted in the PR.

## Non-negotiables

1. **No employer data. Ever.** Personal work on personal equipment. Never add, paste, paraphrase, or anonymize anything from an employer's systems, documents, tickets, chats, workforce data, internal URLs, or proprietary/export-controlled material. No employer names anywhere, no internal acronyms, no realistic HR records. CI's `No employer data` job enforces this from the hashed list in `.github/blocked-terms.sha256` (`harness/scripts/scan_blocked_terms.py`), plus an optional `EMPLOYER_MARKERS` regex secret; do not write blocked terms in plaintext to explain or test it. The author byline names Jeff Otterson and does not name an employer; do not add one. Task sources in `tasks/` are the committed fictional corpus.
2. **Receipts over hype.** Every number in the README, docs, papers, or a PR must be reproducible from a committed command. The receipt mechanism is the three `--check` scripts above (and `validate_submission.py` for a submitted row). Link the command. No "blazing fast", "SOTA", or "production-grade" without a measurement.
3. **Honest benchmarks.** Report nulls and regressions at the same prominence as wins. State n, replicate labels, model + version, date, and cost. The pre-registration is `SPEC.md` plus `seeds/` (committed before scored runs). Do not add a parallel `docs/PREREG.md`. Never tune on the test set. Never delete an inconvenient run; mark it superseded with a reason.
4. **Fail closed.** Gates, validators, and guards deny on error, timeout, missing input, or unparseable output. Never weaken a guard to make a test pass. Never catch-and-ignore exceptions in a decision path.
5. **Tests and CI are the definition of done.** New behavior ships with a test that fails without it. Bug fixes ship with a regression test. Do not lower `--cov-fail-under=90`, mutation results, or scorer `EXPECTED` tables to get green. Do not mark tests `skip`/`xfail` to get green.
6. **Model never grades its own output.** Hard-tier verdicts are mechanical. The soft-tier judge, where used, is a different lineage from the pipeline model (`gpt-5.6-terra`) and both are recorded. There is no xAI/Grok client in this repo.
7. **Irreversible = human-gated.** No force-push, no history rewrite, no publishing, no tagging releases, no posting. Open a PR; a human merges.

## Shell guard

`.cursor/hooks/guard-shell.sh` runs before shell commands matching `git push`, `git reset`, `git rebase`, `git pull`, `git tag`, publish, curl, wget, or `rm -rf`. It fails closed. The matcher includes `git pull`, and the deny rule matches the substring `rebase`, so **`git pull --rebase`** is blocked along with `git rebase`. A payload with no command string is denied. Force-push flags (`--force`, `--force-with-lease`, `-f`, and a short cluster that contains `f`, such as `-fu`) are denied anywhere in that push, including `git push origin --force` and `git push origin -f`. `--hard` is denied anywhere in a reset, including `git reset HEAD --hard`. A newline, `;`, `&&`, or `|` starts a new command, so a later `curl -fsSL` is not a force-push. Tags and publishing are blocked. `git push` and network fetches ask first. Plain `git pull` is allowed. Do not loosen the hook to get a command through.

## Code style

- Harness runtime: Python 3.11+, stdlib-only (`dependencies = []`). Scorers stay 3.9+ and stdlib-only. A new runtime dependency needs a one-line justification in the PR.
- Type hints on public functions. Small pure functions. No global mutable state.
- Raise specific exceptions. No bare `except`. No `except Exception: pass` on a decision path.
- Secrets only via env vars. `.env` is gitignored. Never print secret values.
- Don't commit `__pycache__/`, `*.pyc`, `.coverage`, `.venv/`, `.venv-*/`, or `mutants/`.

## How to work in this repo

- Start non-trivial work in Plan mode. Save the plan to `.cursor/plans/` and link it in the PR.
- Default to one agent. Fan out only for read-heavy, independent work. Writes stay single-threaded per file.
- Keep PRs small (under ~400 changed lines) with one intent. Title: `type(scope): summary`.
- PR body: **What / Why / How verified (commands + output) / Numbers changed (before → after, with command) / Risks / Not done**.
- When you learn something durable, propose an edit to this file or a skill in the same PR.

## Directory map

- `SPEC.md` — frozen metric spec (v0.2.1). `SUBMITTING.md` — third-party row route. `seeds/` — pre-registered replicate ids. `tasks/` — five tasks and fictional assets. `papers/` — wave-1 and wave-2 preprints (text left as published).
- `harness/sabot/` — package (operators, score, adapters, judge, strict floor, uncertainty). `harness/scripts/` — `--check` scorers and live runners. `harness/tests/` — offline suite. `harness/runs/` — published traces (force-tracked). `harness/docs/` — QC ledgers.
- `submissions/` — third-party rows; `TEMPLATE/` is not a row. `docs/` — design notes and decisions.
- `.github/` — CI, CodeQL, Dependabot. `.cursor/` — rules, Bugbot, hooks, MCP, `skills/verify-receipts/`.

## Known traps

- `tests/test_venvs.py` needs the three framework venvs. CI ignores it. Do not install the frameworks in CI, and do not delete the test.
- `judge_live` tests call the `claude` CLI and are deselected by `addopts` in `harness/pyproject.toml`.
- Adapter suites `pytest.importorskip` the frameworks and skip offline. That is expected (15 skips).
- `python scripts/score_wave2.py` rewrites `runs/wave2/WAVE2-RESULTS.md` and strips the hand-appended QC footnote. It has no `--check`. Do not commit that stripped file.
- `harness/.gitignore` ignores `runs/`, but the published corpus is force-tracked. Do not drop it.
- The results field named `seed` is a replicate label (11–15), not an RNG seed passed to the model.
- Coverage omits adapter modules that import only inside framework venvs. The 90 floor is on the stdlib core. Do not lower it and do not delete the omit list to chase a higher number.
