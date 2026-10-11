---
name: verify-receipts
description: Use before opening or updating a PR, or when README/docs numbers change. Re-runs sabot's tests and the existing --check scorers, and writes a receipts block for the PR body.
---

# Verify receipts

Sabot already re-checks its published numbers byte-for-byte. The mechanism is the three `--check` scorers below. Do not add `check_receipts.py`, a README number parser, or a copy of the `EXPECTED` tables.

Run from `harness/`. Capture exit codes and the last ~20 lines of each command.

1. **Tests** (Python 3.11+). This is the CI offline suite, including the coverage floor:

   ```bash
   python -m pip install --upgrade pip "pytest>=8" pytest-cov
   python -m pytest tests/ -q --ignore=tests/test_venvs.py --cov --cov-report=term-missing --cov-fail-under=90
   ```

   `--ignore=tests/test_venvs.py` matches CI: that file needs the pinned framework venvs. Do not delete it. `judge_live` stays deselected via `addopts`.

2. **Receipts** (Python 3.9+, standard library only, no install). A non-zero exit means a published number or a frozen markdown artifact moved:

   ```bash
   python scripts/score_strict.py --check
   python scripts/score_uncertainty.py --check
   python scripts/score_by_operator.py --check
   ```

   Do not edit `EXPECTED`, `STRICT-FLOOR.md`, `UNCERTAINTY.md`, `BY-OPERATOR.md`, or the README to make `--check` pass unless a human asked for a pre-registered rescore. Do not run `score_wave2.py` as a check: it rewrites `WAVE2-RESULTS.md` and strips the QC footnote.

3. **Diff.** `git diff origin/main -- README.md SPEC.md papers/ harness/RESULTS.md harness/runs/wave2/BY-OPERATOR.md harness/runs/wave2/STRICT-FLOOR.md harness/runs/wave2/UNCERTAINTY.md harness/runs/wave2/WAVE2-RESULTS.md`

   List every number that changed. For each, the reproducing command is one of the `--check` scripts (or `python scripts/validate_submission.py <row>` for a third-party submission). If you cannot reproduce it, mark it UNVERIFIED and stop. Do not open the PR as ready.

4. **Employer data and secrets.** Grep the diff for the patterns in `.cursor/rules/40-security-and-data.mdc`. The author byline (README `## Author`, paper headers, `CITATION.cff`) names Jeff Otterson and does not name an employer. Any employer marker, including one added to that byline, is a stop. Report it. Do not "anonymize" it into the repo.

5. **Thresholds.** Confirm `--cov-fail-under` is still 90, no scorer `EXPECTED` entry was edited to match a new output, and no test was skipped, xfailed, or removed to get green.

6. **Write this block** and paste it into the PR's "How verified" section. Never claim a check passed that you did not run.

   ```markdown
   ### Receipts
   - Commands run + pass/fail
   - Numbers: before → after → command → reproduced? (Y/N). "Unchanged" is the expected answer when `--check` is clean.
   - Not verified: live matrix (`setup_venvs.sh`, API keys), `judge_live`, mutation suite (`MUTATION.md`)
   ```
