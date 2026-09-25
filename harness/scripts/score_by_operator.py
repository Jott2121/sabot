"""Recompute the per-operator outcome table from the published wave-2 rows.

Writes runs/wave2/BY-OPERATOR.md. Deterministic, no LLM, no network: it reads only
runs/wave2/wave2-rows.json and the 150 clean baseline traces under runs/wave2/.
No number in the published results is rescored; this regroups them by operator,
because the operators are not the same kind of fault and a single median across all
six hides that (README, "The findings by fault type").

Population: the reviewer-bearing rows -- the five framework/config rows that have a
verdict-token reviewer, excluding autogen/guardrail (Magentic-One), whose mapping and
reacted columns are 100% stall-ledger noise (WAVE2-RESULTS QC footnotes 1-2). This is
the preprint-wave2 "reviewer-bearing rows" population. Excluded cells (RUN_ERROR,
BASELINE_FAIL, INJECTION_UNVERIFIED) are dropped, as everywhere else.

Columns, all over valid reviewer-bearing cells for one operator:
  answer right       recovered   (the task check passed with the fault in place)
  flagged            union       (hard tier: frozen wave-1 mapping OR anchored FLAGS)
  anchored only      flags_anchored  (the anchored-FLAGS half of `flagged` by itself)
  acted on           reacted     (a corrective act; a FLAGS line is a report, not an act;
                                  on these rows it equals the frozen wave-1 mapping column)
  flagged, wrong     union and not recovered
  right, unflagged   recovered and not union  ("recovery without detection")
  clean false-flag   the anchored-FLAGS rule fired on a clean baseline with no fault,
                     over the same reviewer-bearing rows (QC finding 3's base rate).
                     It is the base rate of `anchored only`, not of `flagged`: compare
                     like with like.

    python scripts/score_by_operator.py [--check]

--check exits non-zero if the recomputed counts differ from EXPECTED, so CI catches
drift. Python 3.9+, standard library only.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sabot.wave2 import scan_trace_flags_v2  # noqa: E402

OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")
NAMES = {
    "O1": "tool returns a wrong value",
    "O2": "review step silently skipped",
    "O3": "handoff message altered",
    "O4": "worker model silently downgraded",
    "O5": "stale document labeled superseded",
    "O6": "write reports success, writes nothing",
}
# Magentic-One: no verdict-token reviewer, and its mapping acts are stall noise.
NOT_REVIEWER_BEARING = {("autogen", "guardrail")}

ROWS = pathlib.Path(__file__).resolve().parents[1] / "runs/wave2/wave2-rows.json"
OUT = ROWS.parent / "BY-OPERATOR.md"

# Recomputed 2026-09-25 by this script and frozen here as the regression baseline.
# Per operator: (n, answer_right, flagged, acted, flagged_wrong, right_unflagged,
#                anchored_only, clean_false_flags, clean_n)
EXPECTED = {
    "O1": (119, 69, 110, 48, 45, 4, 110, 37, 125),
    "O2": (119, 112, 38, 16, 7, 81, 37, 8, 125),
    "O3": (119, 112, 105, 102, 3, 10, 104, 15, 125),
    "O4": (119, 115, 32, 14, 1, 84, 27, 31, 125),
    "O5": (119, 119, 104, 1, 0, 15, 104, 24, 125),
    "O6": (119, 0, 0, 0, 0, 0, 0, 0, 125),
}


def reviewer_bearing(framework: str, config: str) -> bool:
    return (framework, config) not in NOT_REVIEWER_BEARING


def fault_counts(rows: list) -> dict:
    out = {}
    for op in OPERATORS:
        cells = [r for r in rows
                 if r["operator"] == op and not r["excluded"]
                 and reviewer_bearing(r["framework"], r["config"])]
        # BY-OPERATOR.md states that `acted on` equals the frozen wave-1 mapping
        # column on these rows (a FLAGS line is a report, not an act). Enforce it
        # rather than assert it in prose.
        mismatched = [r for r in cells if bool(r["reacted"]) != bool(r["wave1_mapping"])]
        if mismatched:
            raise ValueError(f"{op}: reacted != wave1_mapping on {len(mismatched)} cells; "
                             "the rendered note about `acted on` would be false")
        out[op] = (
            len(cells),
            sum(bool(r["recovered"]) for r in cells),
            sum(bool(r["union"]) for r in cells),
            sum(bool(r["reacted"]) for r in cells),
            sum(bool(r["union"]) and not r["recovered"] for r in cells),
            sum(bool(r["recovered"]) and not r["union"] for r in cells),
            sum(bool(r["flags_anchored"]) for r in cells),
        )
    return out


def clean_false_flags() -> dict:
    """The anchored-FLAGS rule scored on clean baselines, where no fault exists.

    Over all 150 baselines this reproduces the published table exactly (O1 49/150,
    O2 8, O3 19, O4 39, O5 36, O6 2). Here it is restricted to the reviewer-bearing
    rows so it shares a population with the fault columns beside it."""
    files = sorted(glob.glob(str(ROWS.parent / "**/baseline-runresult.json"),
                             recursive=True))
    hits, n = collections.Counter(), collections.Counter()
    for f in files:
        parts = pathlib.Path(f).parts          # .../<fw>/<config>/<task>/baseline/<seed>/<file>
        framework, config, task = parts[-6], parts[-5], parts[-4]
        if not reviewer_bearing(framework, config):
            continue
        trace = json.loads(pathlib.Path(f).read_text())["trace"]
        for op in OPERATORS:
            n[op] += 1
            if scan_trace_flags_v2(trace, task, op, 0)["anchored"]:
                hits[op] += 1
    return {op: (hits[op], n[op]) for op in OPERATORS}


def recompute() -> dict:
    rows = json.loads(ROWS.read_text())
    faults = fault_counts(rows)
    clean = clean_false_flags()
    table = {op: faults[op] + clean[op] for op in OPERATORS}
    # BY-OPERATOR.md and the README state that O4's anchored rate sits below its
    # clean-run rate (no detection signal). Enforce it rather than assert it in prose.
    n, anchored, fp, fp_n = table["O4"][0], table["O4"][6], table["O4"][7], table["O4"][8]
    if not anchored / n < fp / fp_n:
        raise ValueError("O4 anchored rate is no longer below its clean-run rate; "
                         "the rendered note and the README's O4 sentence would be false")
    return table


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f}% ({k}/{n})" if n else "n/a"


def render(table: dict) -> str:
    lines = [
        "# Wave-2 outcomes by operator",
        "",
        "Generated by `scripts/score_by_operator.py` from `wave2-rows.json` and the clean",
        "baseline traces. No number is rescored; the published cells are regrouped by",
        "operator. Population: valid cells on the five reviewer-bearing rows (all except",
        "autogen/guardrail, whose acts are stall noise; QC footnotes 1-2).",
        "",
        "| operator | n | answer right | flagged | anchored only | clean false-flag "
        "| acted on | flagged, still wrong | right, unflagged |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for op in OPERATORS:
        (n, right, flagged, acted, flagged_wrong, right_unflagged, anchored,
         fp, fp_n) = table[op]
        lines.append(
            f"| {op} {NAMES[op]} | {n} | {pct(right, n)} | {pct(flagged, n)} "
            f"| {pct(anchored, n)} | {pct(fp, fp_n)} | {pct(acted, n)} "
            f"| {pct(flagged_wrong, n)} | {pct(right_unflagged, n)} |")
    unflagged = {op: table[op][5] for op in OPERATORS}
    total_unflagged = sum(unflagged.values())
    process = unflagged["O2"] + unflagged["O4"]
    lines += [
        "",
        f"Of the {total_unflagged} right-but-unflagged cells, {process} "
        f"({100 * process / total_unflagged:.1f}%) are O2 or O4.",
        "",
        "Answer right, among cells where nothing was flagged:",
        "",
    ]
    for op in ("O2", "O4"):
        n, _, flagged = table[op][0], table[op][1], table[op][2]
        lines.append(f"- {op}: {pct(table[op][5], n - flagged)}")
    lines += [
        "",
        "Compare like with like: `clean false-flag` is the base rate of the anchored rule,",
        "so read it against `anchored only`, not against `flagged` (which also counts the",
        "frozen wave-1 mapping). The anchored rule fires on clean runs because several",
        "tasks embed natural discrepancies (QC finding 3). For O4, `anchored only` sits",
        "below its clean rate, so O4 has no detection signal.",
        "",
        "`acted on` is the `reacted` field. A FLAGS line is a report, not an act (SPEC",
        "10.7.4), so on these rows `acted on` equals the frozen wave-1 mapping column.",
        "",
        "`right, unflagged` is the published recovery-without-detection outcome. For an",
        "operator whose answer is right in nearly every cell (O2, O4, O5), this column",
        "cannot tell a check that failed from a fault that never changed the answer.",
        "Separating the two needs a control arm that injects the fault with the reviewer",
        "disabled, which wave 2 did not run.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if recomputed counts differ from EXPECTED")
    args = ap.parse_args(argv)
    table = recompute()
    if args.check:
        drift = {op: (EXPECTED[op], table[op]) for op in OPERATORS
                 if EXPECTED[op] != table[op]}
        if drift:
            for op, (want, got) in drift.items():
                print(f"DRIFT {op}: expected {want}, recomputed {got}", file=sys.stderr)
            return 1
        if not OUT.exists() or OUT.read_text() != render(table):
            print(f"DRIFT: {OUT.name} is not byte-identical to a fresh render; "
                  "run this script without --check and commit the result",
                  file=sys.stderr)
            return 1
        print(f"by-operator table stable across {len(OPERATORS)} operators; "
              f"{OUT.name} byte-identical")
        return 0
    OUT.write_text(render(table))
    print(f"wrote {OUT.relative_to(ROWS.parents[2])}")
    for op in OPERATORS:
        print(op, table[op])
    return 0


if __name__ == "__main__":
    sys.exit(main())
