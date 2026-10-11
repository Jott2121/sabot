# Bugbot review rules for sabot

Bugbot does not read `.cursor/rules/*.mdc`. It reads this file.

Flag as **blocking**:

1. Any guard, gate, validator, or refusal path that now fails open (returns allow/True/answer on exception, timeout, empty, or malformed input).
2. Lowered thresholds: `--cov-fail-under` (floor is 90), mutation floors, scorer `EXPECTED` tables, or retry/timeout bounds removed.
3. Tests deleted, skipped, xfailed, or assertions weakened without a stated reason in the PR body. `tests/test_venvs.py` ignored in CI, and `judge_live` deselected via `addopts`, are existing and intentional.
4. README, `SPEC.md`, papers, or results numbers that changed without a reproducing command. The receipt commands are `harness/scripts/score_strict.py --check`, `score_uncertainty.py --check`, and `score_by_operator.py --check`. A new parallel checker that re-derives those tables is a bug.
5. Employer or corporate data: company names (Lockheed, LM, LMCO), internal acronyms, CUI/ITAR markings, real-looking employee records, internal URLs. The author byline (README, papers, `CITATION.cff`) names Jeff Otterson and does not name an employer. A new employer mention anywhere else is blocking.
6. Secrets, tokens, `.env` files, or absolute personal paths committed.
7. Unpinned GitHub Actions (must be a full SHA) or widened workflow `permissions:`.
8. Live network or model calls added to the default test path.

Flag as **non-blocking**:

- New runtime dependency without justification. The harness runtime dependency list is empty on purpose.
- Non-deterministic code in scorer or eval paths (unseeded RNG, unordered iteration in hashes or rendered output).
- Exceptions swallowed in non-decision code.

Do not comment on formatting bikesheds or naming. This repo has no ruff config.
