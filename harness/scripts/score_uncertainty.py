"""Put statistical uncertainty on the published wave-2 numbers, from the raw data.

Writes runs/wave2/UNCERTAINTY.md. Deterministic, no LLM, no network, stdlib only: it
reads runs/wave2/wave2-rows.json (the 825 scored wave-2 cells), the 150 clean
baseline traces under runs/wave2/, and the frozen wave-1 matrix under runs/matrix/.

    python scripts/score_uncertainty.py [--check]

--check regenerates and (a) compares the pinned intervals against this file's frozen
EXPECTED table and (b) diffs the full rendered text against the committed
UNCERTAINTY.md, exiting non-zero on either kind of drift. Same interface and same
drift-guard contract as scripts/score_strict.py.

This script CHANGES NO PUBLISHED POINT ESTIMATE. Every point column it prints is
recomputed from the raw data and must agree with what is already published; the new
material is the interval columns. The estimator, its clustering rationale and its
limits live in sabot/uncertainty.py.
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
import pathlib
import sys
import textwrap

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from sabot.strict import strict_detected  # noqa: E402
from sabot.uncertainty import (Estimate, cluster_ids, contrast_stat, diff_stat,  # noqa: E402
                               estimate, median_stat, monte_carlo_resamples,
                               per_cluster_values, rate_stat, sign_counts, sign_test_p,
                               tabulate)
from sabot.wave2 import scan_trace_flags_v2  # noqa: E402

HARNESS = pathlib.Path(__file__).resolve().parents[1]
ROWS = HARNESS / "runs/wave2/wave2-rows.json"
MATRIX = HARNESS / "runs/matrix"
OUT = ROWS.parent / "UNCERTAINTY.md"

WIDTH = 79
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")
FRAMEWORKS = ("autogen", "crewai", "langgraph")
ROW_KEYS = ("langgraph/default", "langgraph/guardrail", "crewai/default",
            "crewai/guardrail", "autogen/default", "autogen/guardrail")
STANDARD_ROWS = tuple(k for k in ROW_KEYS if k != "autogen/guardrail")
MAGENTIC = "autogen/guardrail"
FW_ROWS = {fw: [k for k in ROW_KEYS if k.startswith(fw + "/")] for fw in FRAMEWORKS}
PUBLISHED_BASE_RATES = {"O1": "32.7%", "O2": "5.3%", "O3": "12.7%",
                        "O4": "26.0%", "O5": "24.0%", "O6": "1.3%"}

# Recomputed 2026-07-24 by this script and frozen here as the regression baseline, the
# way scripts/score_strict.py freezes its floors. Values are (point, lo, hi) rounded to
# 4 decimals; --check fails on any movement at that resolution.
EXPECTED = {
    "wave1_median": (16.6667, 15.6463, 17.7536),
    "wave2_median": (54.9645, 52.3256, 58.0),
    "median_contrast": (38.2979, 36.375, 40.6241),
    "paired_pooled_effect": (39.3939, 36.9748, 41.3605),
    "union/langgraph/default": (55.0725, 51.5873, 58.0),
    "union/langgraph/guardrail": (54.8611, 51.3889, 58.0),
    "union/crewai/default": (53.3333, 49.3333, 57.3333),
    "union/crewai/guardrail": (53.6232, 51.3889, 56.0606),
    "union/autogen/default": (55.5556, 52.1739, 59.7222),
    "union/autogen/guardrail": (84.7222, 77.7778, 91.3043),
    "strict/langgraph/default": (47.8261, 43.6508, 51.3333),
    "strict/langgraph/guardrail": (48.6111, 43.1818, 52.6667),
    "strict/crewai/default": (51.3333, 48.6667, 54.6667),
    "strict/crewai/guardrail": (52.1739, 48.6111, 55.5556),
    "strict/autogen/default": (52.7778, 49.2063, 56.6667),
    "strict/autogen/guardrail": (55.5556, 50.6667, 59.7222),
    "magentic_flags_only": (73.6111, 69.3333, 78.7879),
    "o4_honest_mapping_only": (9.7902, 4.2857, 13.986),
    "o4_fault_anchored": (24.4755, 20.2797, 28.6713),
    "o4_clean_base": (26.0, 23.3333, 28.6667),
    # The O4 null as a CONTRAST rather than two overlapping intervals. Both straddle
    # zero, and the sign flips between them — see the section-4 disclosure.
    "o4_contrast": (-1.5245, -7.3333, 4.0047),
    "o4_matched_contrast": (1.3986, -4.0816, 6.2937),
    "rwd_union": (26.0814, 24.8462, 27.8215),
    "rwd_frozen": (50.0, 49.0775, 51.0582),
}

CAVEAT_MAGENTIC = (
    "Magentic (autogen/guardrail) rows carry the wave-2 QC caveats wherever they "
    "appear: the row's 84.7% union is the permissive pre-registered mapping reading, "
    "whose Magentic acts are 100% stall-ledger noise, so **73.6% flags-only is the "
    "honest number for the row** (QC finding 1); the row is scored over the "
    "pre-registered Magentic carve-out subset (O1/O4/O5 only, 72 cells, SPEC 10.6), "
    "not the full operator suite; its wave-1 comparator is ~0% true detection either "
    "way (wave-1 footnote 5); and the FLAGS contract itself induces Magentic stalls "
    "(QC finding 2). An interval around a number does not launder any of that — it is "
    "an interval around a caveated number."
)


# --- loading ---------------------------------------------------------------------------

def load_wave2():
    return [r for r in json.loads(ROWS.read_text()) if r["excluded"] is None]


def load_wave1_matrix():
    """The frozen wave-1 matrix, from which the published 16.7% median is recomputed."""
    rows = []
    for path in sorted(glob.glob(str(MATRIX / "*/*/*/*/seed*/cellverdict.json"))):
        parts = pathlib.Path(path).parts
        verdict = json.loads(pathlib.Path(path).read_text())
        if verdict["excluded"] is not None:
            continue
        rows.append({"framework": parts[-6], "config": parts[-5], "task": parts[-4],
                     "operator": parts[-3], "seed": int(parts[-2][len("seed"):]),
                     "hard": verdict["detected_hard"]})
    return rows


def load_clean_baselines():
    """One row per (clean baseline run x operator): the anchor rule with no fault present.

    There are 150 baseline runs, one per (framework, config, task, replicate) group, and
    the matrix driver reuses each across all of that group's operator cells — the shared
    structure that justifies clustering on the replicate at all.
    """
    rows = []
    for path in sorted(glob.glob(str(ROWS.parent / "**/baseline-runresult.json"),
                                 recursive=True)):
        parts = pathlib.Path(path).parts
        framework, config, task = parts[-6], parts[-5], parts[-4]
        seed = int(parts[-2][len("seed"):])
        trace = json.loads(pathlib.Path(path).read_text())["trace"]
        for operator in OPERATORS:
            rows.append({"framework": framework, "config": config, "task": task,
                         "operator": operator, "seed": seed,
                         "anchored": scan_trace_flags_v2(trace, task, operator,
                                                         0)["anchored"]})
    return rows


def group_key(row):
    """The (framework, config, task, replicate) group that shares one cached baseline."""
    return (row["framework"], row["config"], row["task"], row["seed"])


# --- small rendering helpers -----------------------------------------------------------

def pct(value: float, sign: bool = False) -> str:
    return "{:+.1f} pp".format(value) if sign else "{:.1f}%".format(value)


def interval(e: Estimate, sign: bool = False) -> str:
    spec = "+.1f" if sign else ".1f"
    return "[{:{s}}, {:{s}}]".format(e.lo, e.hi, s=spec)


def jack(e: Estimate, sign: bool = False) -> str:
    spec = "+.1f" if sign else ".1f"
    return "{:{s}} to {:{s}}".format(e.jack_lo, e.jack_hi, s=spec)


def counted(table, groups, metric, clusters) -> str:
    hits = sum(table[g][c][metric] for g in groups for c in clusters)
    n = sum(table[g][c]["n"] for g in groups for c in clusters)
    return "{}/{}".format(hits, n)


def total_n(table, groups, clusters) -> int:
    return sum(table[g][c]["n"] for g in groups for c in clusters)


class Report:
    """Accumulates markdown lines and, separately, every interval it has published, so
    the "widest intervals" section is derived from the file rather than hand-picked."""

    def __init__(self):
        self.lines = []
        self.tracked = []

    def line(self, text=""):
        self.lines.append(text)

    def para(self, text):
        self.lines.extend(textwrap.wrap(text, WIDTH, break_long_words=False,
                                        break_on_hyphens=False))
        self.lines.append("")

    def item(self, text, bullet="* ", indent="  "):
        self.lines.extend(textwrap.wrap(text, WIDTH, initial_indent=bullet,
                                        subsequent_indent=indent,
                                        break_long_words=False, break_on_hyphens=False))

    def track(self, label, e, sign=False):
        self.tracked.append((label, e, sign))
        return e

    def text(self):
        return "\n".join(self.lines)


# --- the report ------------------------------------------------------------------------

def render():
    w2 = load_wave2()
    w1 = load_wave1_matrix()
    base = load_clean_baselines()
    clusters = cluster_ids(w2)
    k = len(clusters)
    if cluster_ids(w1) != clusters or cluster_ids(base) != clusters:
        raise SystemExit("wave-1 and wave-2 replicate label sets differ; the contrast "
                         "is not replicate-matched and this report's method does "
                         "not apply")

    def row_of(r):
        return "{}/{}".format(r["framework"], r["config"])

    t2 = tabulate(w2, row_of, {
        "union": lambda r: int(r["union"]),
        "flags": lambda r: int(r["flags_anchored"]),
        "strict": lambda r: int(strict_detected(r)),
        "honest": lambda r: int(r["flags_anchored"] if row_of(r) == MAGENTIC
                                else r["union"]),
        "rwd_union": lambda r: int(r["recovered"] and not r["union"]),
        "rwd_frozen": lambda r: int(r["recovered"] and not r["wave1_mapping"]),
    }, clusters)
    t1 = tabulate(w1, row_of, {"hard": lambda r: int(r["hard"])}, clusters)
    # Paired grid: wave-2 cells that have a scored wave-1 partner on the SAME cell.
    tp = tabulate(w2, lambda r: row_of(r) if r["wave1_hard"] is not None else None, {
        "union": lambda r: int(r["union"]),
        "flags": lambda r: int(r["flags_anchored"]),
        "w1": lambda r: int(r["wave1_hard"]),
    }, clusters)
    t4 = tabulate([r for r in w2 if r["operator"] == "O4"], lambda r: "O4", {
        "flags": lambda r: int(r["flags_anchored"]),
        "honest": lambda r: int(strict_detected(r)),
    }, clusters)
    tb = tabulate(base, lambda r: r["operator"],
                  {"anchored": lambda r: int(r["anchored"])}, clusters)
    # Matched O4 arms: every group has exactly one O4 cell and exactly one cached
    # baseline run, so each surviving O4 fault cell pairs 1:1 with its OWN baseline.
    o4_baseline = {group_key(r): int(r["anchored"]) for r in base
                   if r["operator"] == "O4"}
    o4_rows = [r for r in w2 if r["operator"] == "O4"]
    if len(o4_baseline) != len(base) // len(OPERATORS):
        raise SystemExit("clean baselines are not one per group; the matched O4 "
                         "contrast's 1:1 pairing does not hold")
    tm = tabulate([{"seed": r["seed"], "fault": int(r["flags_anchored"]),
                    "base": o4_baseline[group_key(r)]} for r in o4_rows],
                  lambda r: "O4",
                  {"fault": lambda r: r["fault"], "base": lambda r: r["base"]}, clusters)

    n2, n1, npair = (total_n(t2, ROW_KEYS, clusters), total_n(t1, ROW_KEYS, clusters),
                     total_n(tp, ROW_KEYS, clusters))

    w1_median = median_stat([rate_stat(t1, FW_ROWS[f], "hard", clusters)
                             for f in FRAMEWORKS])
    w2_median = median_stat([rate_stat(t2, FW_ROWS[f], "union", clusters)
                             for f in FRAMEWORKS])
    honest_median = median_stat([rate_stat(t2, FW_ROWS[f], "honest", clusters)
                                 for f in FRAMEWORKS])

    key = {}
    R = Report()

    R.line("# Sabot — statistical uncertainty for the wave-2 results (SPEC v0.2.1)")
    R.line()
    R.para("Regenerate with `python scripts/score_uncertainty.py`; `--check` fails on "
           "drift. Deterministic, no LLM, no network, Python 3.9+ standard library "
           "only. Reads only `wave2-rows.json`, the 150 clean baseline traces under "
           "`runs/wave2/`, and the frozen wave-1 matrix under `runs/matrix/`.")
    R.para("**Nothing here moves a published number.** Every point column below is "
           "recomputed from the raw data and reproduces what is already published; the "
           "new material is the interval columns. This file closes the one substantive "
           "gap an external reviewer named in the wave-2 package: every published "
           "figure was a point estimate over 5 replicates with correlated cells, carrying "
           "no confidence intervals and no paired effect estimates.")

    # --- method -------------------------------------------------------------------
    R.line("## Method")
    R.line()
    R.para("**The field named `seed` is a replicate label, not a random seed.** This has "
           "to come first, because the word invites a claim this design cannot make. "
           "The values {s} were never passed to the pipeline model and never passed to "
           "any RNG. All three adapters construct their client from a model id alone — "
           "`ChatOpenAI(model=model_id)`, `LLM(model=f\"openai/{{model_id}}\")`, "
           "`OpenAIChatCompletionClient(model=model_id)` — with no `seed` and no "
           "`temperature` kwarg, and `Cell.seed` reaches only run-id strings, recorder "
           "metadata and output paths. The pre-registered seeds file already says so in "
           "its own rule text: \"Seeds are repetition identifiers recorded per run.\" "
           "That is all they are: **{k} stochastic repetitions of the whole matrix, "
           "carrying labels**. Everything below is therefore a "
           "{k}-replicate design — a {k}-matrix sensitivity analysis — and this file "
           "says replicate, replicate-cluster bootstrap, replicate-jackknife throughout."
           .format(k=k, s=", ".join(str(c) for c in clusters)))
    R.para("**Unit of observation vs unit of resampling.** The scoreboard's unit is a "
           "CELL (framework x config x task x operator x replicate). Cells are not "
           "independent, so a binomial interval over the {n} valid wave-2 cells would "
           "treat {n} correlated observations as {n} independent ones and would be far "
           "too narrow.".format(n=n2))
    R.para("**So the bootstrap resamples REPLICATES, not cells — and the reason is "
           "structural, not stochastic.** `scripts/run_matrix.py` caches ONE no-fault "
           "baseline run per (framework, config, task, replicate) group and reuses it "
           "for every operator cell in that group. The exclusion decision, the "
           "`recovered` comparison and the clean-run comparator of up to six cells all "
           "descend from that single shared run. That is a real dependence structure "
           "the design induces, it lines up exactly with the replicate label, and "
           "resampling whole replicates preserves it. The clustering is earned by the "
           "shared baseline — not by model-level randomness, of which there is none to "
           "point at. Each resample draws {k} replicates with replacement and recomputes "
           "every rate from the cells those replicates contributed.".format(k=k))
    R.para("**On pairing wave 1 to wave 2.** Wave 2 reuses wave 1's registered labels "
           "verbatim (seeds/wave2.json), and this file matches repetition 13 to "
           "repetition 13. That match is **arbitrary but unbiased**: repetition 13 of a "
           "cell in wave 1 has no special affinity with repetition 13 of the same cell "
           "in wave 2, because the labels drove nothing. What carries the paired "
           "estimate is matching by CELL — same framework, config, task and operator, "
           "wave-1 rules against wave-2 rules. The label match only fixes which of the "
           "{k} repetitions pairs with which, and any other 1:1 assignment would be "
           "equally valid in expectation.".format(k=k))
    mc = estimate(w2_median, k, resamples=monte_carlo_resamples(k))
    R.para("**The intervals are exact, not simulated.** A size-{k} resample with "
           "replacement of {k} clusters has only C({a}, {b}) = 126 distinct multisets "
           "({k}**{k} = {t} ordered draws). This script enumerates all 126 with their "
           "exact multinomial weights, so the percentile CIs below carry **zero "
           "Monte-Carlo error**. Cross-check: an ordinary Monte-Carlo cluster "
           "bootstrap (20,000 draws, fixed documented RNG seed — the analysis's own, "
           "not the data's) puts the headline median "
           "CI at [{lo:.1f}, {hi:.1f}] against the exact [{elo:.1f}, {ehi:.1f}]."
           .format(k=k, a=2 * k - 1, b=k - 1, t=k ** k, lo=mc.lo, hi=mc.hi,
                   elo=estimate(w2_median, k).lo, ehi=estimate(w2_median, k).hi))
    R.para("**Discreteness is the price, and it is stated per number.** With at most "
           "126 support points a 2.5/97.5 percentile is read off a coarse lattice. "
           "Percentiles use the type-1 (inverse-CDF) definition — the smallest value "
           "whose cumulative weight reaches the tail probability — so every endpoint "
           "is a value the bootstrap actually produced; interpolating would invent "
           "resolution this design does not have. The `support` column publishes how "
           "many DISTINCT values each statistic's bootstrap distribution has, so a "
           "reader can see exactly how coarse each interval is. Two companions travel "
           "with the CI for the same reason:")
    R.item("**Replicate-jackknife range** — the exact min and max over the {} "
           "leave-one-replicate-out datasets. Not a rival interval: it answers \"how "
           "far does dropping any one repetition move this number?\", which a "
           "percentile cannot.".format(k))
    R.item("**Bootstrap range** — the min and max attainable over all 126 resamples, "
           "i.e. what the number becomes in the degenerate case where all {} draws "
           "land on a single replicate.".format(k))
    R.line()
    R.para("**A sign test on {k} replicates cannot reach p < 0.05.** The most extreme "
           "possible outcome ({k}/{k} replicates agreeing) has a two-sided exact p of "
           "2/2**{k} = {p:.4f}. The per-replicate columns below are therefore "
           "**descriptions of direction, never significance claims**, and this file "
           "states that arithmetic rather than letting a reader assume otherwise."
           .format(k=k, p=sign_test_p(k, k)))
    R.para("**What replicate resampling cannot capture.** It captures "
           "repetition-to-repetition sampling "
           "variation at fixed everything-else. It does **not** capture pipeline-model "
           "version drift, framework version drift, task-suite selection (5 tasks), or "
           "operator-suite selection (6 operators). Those are fixed constants of this "
           "design, not sampled populations, and no resampling of {} replicates can put an "
           "interval on them. The README's standing caveat still governs: these are "
           "results about these frameworks with this model at these versions, not laws "
           "of nature.".format(k))

    # --- 1. headline ---------------------------------------------------------------
    R.line("## 1. The headline contrast: 16.7% -> 55.0%")
    R.line()
    R.para("Both medians are the pre-registered aggregator (SPEC section 7): the median "
           "across the three FRAMEWORKS with configs pooled.")
    R.line("| quantity | point | 95% cluster-bootstrap CI | replicate-jackknife range "
           "| bootstrap range | support |")
    R.line("|---|---|---|---|---|---|")
    key["wave1_median"] = R.track(
        "wave-1 median hard-tier", estimate(w1_median, k))
    key["wave2_median"] = R.track(
        "wave-2 median union (the headline)", estimate(w2_median, k))
    key["median_contrast"] = R.track(
        "replicate-matched difference of medians",
        estimate(contrast_stat(w2_median, w1_median), k), sign=True)
    key["paired_pooled_effect"] = R.track(
        "pooled per-cell paired effect",
        estimate(diff_stat(tp, list(ROW_KEYS), "union", "w1", clusters), k), sign=True)
    headline_rows = [
        ("wave-1 median hard-tier (frozen matrix, {} valid cells)".format(n1),
         key["wave1_median"], False),
        ("wave-2 median union (published headline, {} valid cells)".format(n2),
         key["wave2_median"], False),
        ("replicate-matched difference of medians", key["median_contrast"], True),
        ("strictly per-cell paired effect ({} paired cells)".format(npair),
         key["paired_pooled_effect"], True),
    ]
    for label, e, sign in headline_rows:
        spec = "+.1f" if sign else ".1f"
        R.line("| {} | **{}** | {} | {} | {:{s}} to {:{s}} | {} |".format(
            label, pct(e.point, sign), interval(e, sign), jack(e, sign),
            e.dist_min, e.dist_max, e.support, s=spec))
    R.line()
    R.para("The two effect rows answer different questions and both are reported. The "
           "**difference of medians** puts an interval on the contrast exactly as "
           "published (wave-1's median over its own {n1} valid cells, wave-2's over "
           "its {n2}), replicate-matched because one drawn label multiset feeds both. "
           "The **strictly per-cell paired** effect is the reviewer's estimand: the "
           "mean of `wave2_union - wave1_hard` over the {np} cells that have a scored "
           "wave-1 partner, so each cell is its own control (same framework, config, "
           "task, operator and replicate; wave-1 rules vs wave-2 rules). It runs on a "
           "slightly smaller population — {d} of the {n2} valid wave-2 cells have no "
           "wave-1 partner, from the wave-2 O4 landing-probe exclusions and the wave-1 "
           "BASELINE_FAIL exclusions — which is why its point value differs slightly "
           "from the difference of medians. Neither replaces a published number."
           .format(n1=n1, n2=n2, np=npair, d=n2 - npair))
    R.para("**Both intervals exclude zero by a wide margin.** With five replicates that "
           "is "
           "about as strong as this design can state it; see the limitations for what "
           "the interval does and does not cover.")

    # --- 2. rows -------------------------------------------------------------------
    R.line("## 2. Wave-2 detection by framework x config, with the strict floor")
    R.line()
    R.para("The README's convention is that the strict injection-evidence floor and the "
           "published union are quoted as a **pair**, with the truth in between. Both "
           "now carry intervals, computed on the same resamples.")
    R.line("| row | valid | published union | 95% CI | jackknife range | support "
           "| strict floor | 95% CI |")
    R.line("|---|---|---|---|---|---|---|---|")
    for row in ROW_KEYS:
        u = key["union/" + row] = R.track(
            "{} union".format(row), estimate(rate_stat(t2, [row], "union", clusters), k))
        s = key["strict/" + row] = R.track(
            "{} strict floor".format(row),
            estimate(rate_stat(t2, [row], "strict", clusters), k))
        R.line("| {} | {} | **{}** ({}) | {} | {} | {} | {} ({}) | {} |".format(
            row, total_n(t2, [row], clusters), pct(u.point),
            counted(t2, [row], "union", clusters), interval(u), jack(u), u.support,
            pct(s.point), counted(t2, [row], "strict", clusters), interval(s)))
    R.line()
    R.line("### The five standard rows are not distinguishable under this analysis")
    R.line()
    R.para("Every pairwise replicate-matched difference between the five standard rows "
           "has a 95% CI containing zero. The 53.3-55.6% spread across those rows is "
           "**not** evidence that any framework or config detects better than another; "
           "it sits inside repetition noise. That is a limitation of five replicates, "
           "not a finding about the frameworks.")
    R.line("| comparison | difference | 95% CI | contains 0 |")
    R.line("|---|---|---|---|")
    pairwise = []
    for i, a in enumerate(STANDARD_ROWS):
        for b in STANDARD_ROWS[i + 1:]:
            e = R.track("{} - {} (union)".format(a, b),
                        estimate(contrast_stat(rate_stat(t2, [a], "union", clusters),
                                               rate_stat(t2, [b], "union", clusters)), k),
                        sign=True)
            pairwise.append(e)
            R.line("| {} - {} | {} | {} | {} |".format(
                a, b, pct(e.point, True), interval(e, True),
                "yes" if e.lo <= 0 <= e.hi else "**NO**"))
    R.line()
    R.para("All {} comparisons contain zero.".format(len(pairwise))
           if all(e.lo <= 0 <= e.hi for e in pairwise)
           else "**Not every comparison contains zero — read the table.**")
    R.para("One entry deserves its own note, because its interval is degenerate rather "
           "than informative: `langgraph/default` and `langgraph/guardrail` have the "
           "**identical per-replicate union rate on all five replicates** (56.7, 50.0, 60.0, "
           "56.7, 50.0). Their +0.2 pp pooled difference is therefore purely a "
           "denominator artifact — 138 vs 144 valid cells, from wave-2 exclusions — "
           "and no resample can push it below zero, which is why its lower endpoint "
           "is exactly 0.0 rather than negative.")
    R.line("### Pooled by framework — the three inputs to the median")
    R.line()
    R.line("| framework | valid | pooled union | 95% CI | jackknife range | support |")
    R.line("|---|---|---|---|---|---|")
    for fw in FRAMEWORKS:
        e = R.track("{} pooled union".format(fw),
                    estimate(rate_stat(t2, FW_ROWS[fw], "union", clusters), k))
        R.line("| {} | {} | **{}** ({}) | {} | {} | {} |".format(
            fw, total_n(t2, FW_ROWS[fw], clusters), pct(e.point),
            counted(t2, FW_ROWS[fw], "union", clusters), interval(e), jack(e), e.support))
    R.line()

    # --- 3. paired effects ---------------------------------------------------------
    R.line("## 3. Paired per-framework effects (the reviewer's specific ask)")
    R.line()
    R.para("Per row, the mean per-cell paired difference `wave2_union - wave1_hard` "
           "over the cells that have a scored wave-1 partner. The `wave-1 hard` column "
           "here is the same paired column the README publishes.")
    R.line("| row | paired cells | wave-1 hard | wave-2 union | paired effect | 95% CI "
           "| jackknife range | per-replicate effects (pp) | replicates positive "
           "| exact sign p |")
    R.line("|---|---|---|---|---|---|---|---|---|---|")
    for row in ROW_KEYS:
        stat = diff_stat(tp, [row], "union", "w1", clusters)
        e = key["paired/" + row] = R.track("{} paired effect".format(row),
                                           estimate(stat, k), sign=True)
        per = per_cluster_values(stat, k)
        positive, _, _ = sign_counts(per)
        n = total_n(tp, [row], clusters)
        w1_hits = sum(tp[row][c]["w1"] for c in clusters)
        w2_hits = sum(tp[row][c]["union"] for c in clusters)
        R.line("| {} | {} | {} ({}/{}) | {} ({}/{}) | **{}** | {} | {} | {} | {}/{} "
               "| {:.4f} |".format(
                   row, n, pct(100.0 * w1_hits / n), w1_hits, n,
                   pct(100.0 * w2_hits / n), w2_hits, n, pct(e.point, True),
                   interval(e, True), jack(e, True),
                   ", ".join("{:+.1f}".format(v) for v in per), positive, k,
                   sign_test_p(positive, k)))
    R.line()
    R.para("**Every row: all {k}/{k} replicates positive, every 95% CI strictly above "
           "zero.** Read that as direction and consistency, not as p < 0.05 — the "
           "exact sign-test p of {p:.4f} is the FLOOR of what {k} replicates can produce, "
           "and it is reported at that floor on every row precisely because the test "
           "is saturated, not because the effect is marginal. The CI, which uses the "
           "magnitudes rather than only the signs, is the informative statement here."
           .format(k=k, p=sign_test_p(k, k)))
    R.para("**The Magentic row's paired effect must be read against its carve-out.** "
           "Its {} paired cells are the pre-registered carve-out subset only (O1/O4/O5; "
           "SPEC 10.6), so its effect is not comparable cell-for-cell with the standard "
           "rows, which pair across all six operators. {}"
           .format(total_n(tp, [MAGENTIC], clusters), CAVEAT_MAGENTIC))
    R.line("### The Magentic row on its honest (flags-only) surface")
    R.line()
    R.line("| quantity | point | 95% CI | jackknife range | support |")
    R.line("|---|---|---|---|---|")
    e = key["magentic_flags_only"] = R.track(
        "Magentic flags-only detection",
        estimate(rate_stat(t2, [MAGENTIC], "flags", clusters), k))
    R.line("| Magentic flags-only detection (the quoted number) | **{}** ({}) | {} | {} "
           "| {} |".format(pct(e.point), counted(t2, [MAGENTIC], "flags", clusters),
                           interval(e), jack(e), e.support))
    mag_stat = diff_stat(tp, [MAGENTIC], "flags", "w1", clusters)
    e = R.track("Magentic paired effect, flags-only", estimate(mag_stat, k), sign=True)
    per = per_cluster_values(mag_stat, k)
    positive, _, _ = sign_counts(per)
    R.line("| Magentic paired effect, flags-only vs wave-1 hard | **{}** | {} | {} | {} |"
           .format(pct(e.point, True), interval(e, True), jack(e, True), e.support))
    R.line()
    R.para("Per-replicate effects on that surface: {}; {}/{} positive. The flags-only "
           "surface is the one to quote: it is the honest reading of the row and it "
           "drops the 8 union-only cells that fire on stall noise alone."
           .format(", ".join("{:+.1f}".format(v) for v in per), positive, k))

    # --- 4. the other published numbers --------------------------------------------
    R.line("## 4. Intervals for the other published wave-2 numbers")
    R.line()
    key["rwd_union"] = R.track("recovery-without-detection, union surface",
                               estimate(rate_stat(t2, list(ROW_KEYS), "rwd_union",
                                                  clusters), k))
    key["rwd_frozen"] = R.track("recovery-without-detection, frozen wave-1 surface",
                                estimate(rate_stat(t2, list(ROW_KEYS), "rwd_frozen",
                                                   clusters), k))
    key["o4_honest_mapping_only"] = R.track(
        "O4 honest reading (mapping-only)", estimate(rate_stat(t4, ["O4"], "honest",
                                                               clusters), k))
    key["o4_fault_anchored"] = R.track(
        "O4 anchored-flags rate on fault runs",
        estimate(rate_stat(t4, ["O4"], "flags", clusters), k))
    key["o4_clean_base"] = R.track(
        "O4 clean-baseline false-anchor base rate",
        estimate(rate_stat(tb, ["O4"], "anchored", clusters), k))
    R.line("| published number | as published | point | 95% CI | jackknife range "
           "| support |")
    R.line("|---|---|---|---|---|---|")
    for label, published, name in (
            ("recovery-without-detection, union surface", "26.1%", "rwd_union"),
            ("recovery-without-detection, frozen wave-1 surface", "50.0%", "rwd_frozen"),
            ("Magentic flags-only detection", "73.6%", "magentic_flags_only"),
            ("O4 honest reading (mapping-only, Magentic stall acts zeroed)", "9.8%",
             "o4_honest_mapping_only"),
            ("O4 anchored-flags rate on fault runs", "24.5%", "o4_fault_anchored"),
            ("O4 clean-baseline false-anchor base rate", "26.0%", "o4_clean_base")):
        e = key[name]
        R.line("| {} | {} | {} | {} | {} | {} |".format(
            label, published, pct(e.point), interval(e), jack(e), e.support))
    R.line()
    R.line("### The O4 null, stated as a contrast rather than as two intervals")
    R.line()
    R.para("Two overlapping intervals are not a test. Overlap is neither necessary nor "
           "sufficient for a null, so the O4 claim is made here the only way it should "
           "be: as **one contrast with its own interval**, fault runs minus clean "
           "baselines on the same anchored-flag surface, resampled over the same "
           "replicate clusters as everything else in this file.")
    R.line("| contrast | fault arm | clean arm | difference | 95% CI | jackknife range "
           "| support |")
    R.line("|---|---|---|---|---|---|---|")
    key["o4_contrast"] = R.track(
        "O4 fault-minus-clean contrast (published denominators)",
        estimate(contrast_stat(rate_stat(t4, ["O4"], "flags", clusters),
                               rate_stat(tb, ["O4"], "anchored", clusters)), k),
        sign=True)
    matched_stat = diff_stat(tm, ["O4"], "fault", "base", clusters)
    key["o4_matched_contrast"] = R.track(
        "O4 fault-minus-clean contrast (matched groups)",
        estimate(matched_stat, k), sign=True)
    n_matched = total_n(tm, ["O4"], clusters)
    for label, e, fault_arm, clean_arm in (
            ("as published ({} fault cells vs all {} baselines)".format(
                total_n(t4, ["O4"], clusters), total_n(tb, ["O4"], clusters)),
             key["o4_contrast"],
             "{} ({})".format(pct(key["o4_fault_anchored"].point),
                              counted(t4, ["O4"], "flags", clusters)),
             "{} ({})".format(pct(key["o4_clean_base"].point),
                              counted(tb, ["O4"], "anchored", clusters))),
            ("matched groups ({} O4 cells each against ITS OWN cached baseline)".format(
                n_matched), key["o4_matched_contrast"],
             "{} ({})".format(pct(100.0 * sum(tm["O4"][c]["fault"] for c in clusters)
                                  / n_matched),
                              counted(tm, ["O4"], "fault", clusters)),
             "{} ({})".format(pct(100.0 * sum(tm["O4"][c]["base"] for c in clusters)
                                  / n_matched),
                              counted(tm, ["O4"], "base", clusters)))):
        R.line("| {} | {} | {} | **{}** | {} | {} | {} |".format(
            label, fault_arm, clean_arm, pct(e.point, True), interval(e, True),
            jack(e, True), e.support))
    R.line()
    matched_per = per_cluster_values(matched_stat, k)
    matched_pos, matched_neg, _ = sign_counts(matched_per)
    R.para("**Both contrasts are null, and the sign of the effect is not even stable "
           "across them.** The as-published contrast is {a} and the matched-group "
           "contrast is {b} — opposite signs, both intervals straddling zero by a wide "
           "margin. The per-replicate matched differences are {p}, {pos} positive and "
           "{neg} negative out of {k} (exact two-sided sign p = {sp:.4f}). An effect "
           "whose direction flips when you fix a denominator mismatch is not an effect."
           .format(a=pct(key["o4_contrast"].point, True) + " "
                     + interval(key["o4_contrast"], True),
                   b=pct(key["o4_matched_contrast"].point, True) + " "
                     + interval(key["o4_matched_contrast"], True),
                   p=", ".join("{:+.1f}".format(v) for v in matched_per),
                   pos=matched_pos, neg=matched_neg, k=k,
                   sp=sign_test_p(matched_pos, k)))
    R.para("The two rows differ only in the clean arm's denominator, and that difference "
           "is worth disclosing rather than picking a winner. The as-published contrast "
           "compares {f} valid O4 fault cells against all {b} baseline runs, including "
           "the {d} groups whose O4 fault cell was excluded — and those {d} groups "
           "contribute {x} of the {y} baseline anchors, so they are not a neutral "
           "addition. The matched row removes the mismatch by scoring each surviving O4 "
           "cell against the baseline run its own group actually cached. Neither is "
           "wrong; the as-published row is the direct contrast between the two figures "
           "the wave-2 package prints, and the matched row is the cleaner estimand."
           .format(f=total_n(t4, ["O4"], clusters), b=total_n(tb, ["O4"], clusters),
                   d=total_n(tb, ["O4"], clusters) - n_matched,
                   x=(sum(tb["O4"][c]["anchored"] for c in clusters)
                      - sum(tm["O4"][c]["base"] for c in clusters)),
                   y=sum(tb["O4"][c]["anchored"] for c in clusters)))
    R.para("**A null contrast is not equivalence.** Neither interval establishes that "
           "the O4 flag surface behaves identically with and without a fault; both are "
           "consistent with effects of several percentage points in either direction. "
           "Establishing equivalence requires an equivalence margin declared in advance, "
           "and **no equivalence margin was pre-declared** — not in SPEC v0.2.0, not in "
           "the QC ledger, not here. The honest statement is the weaker one the wave-2 "
           "package already makes: the O4 anchored-flags surface shows no detectable "
           "signal over its own clean-run base rate, so the honest O4 number is the "
           "mapping-only {}.".format(pct(key["o4_honest_mapping_only"].point)))
    R.line("### Clean-baseline false-anchor base rates, with intervals")
    R.line()
    R.para("The published base-rate table (QC finding 3), recomputed over the same 150 "
           "clean baseline runs with a replicate-cluster CI on each rate. These are the "
           "comparators every anchored-text detection number must be read against.")
    R.line("| operator | published | point | 95% CI | jackknife range | support |")
    R.line("|---|---|---|---|---|---|")
    for operator in OPERATORS:
        e = R.track("{} clean-baseline false-anchor base rate".format(operator),
                    estimate(rate_stat(tb, [operator], "anchored", clusters), k))
        R.line("| {} | {} | {} ({}) | {} | {} | {} |".format(
            operator, PUBLISHED_BASE_RATES[operator], pct(e.point),
            counted(tb, [operator], "anchored", clusters), interval(e), jack(e),
            e.support))
    R.line()

    # --- 5. robustness -------------------------------------------------------------
    R.line("## 5. Is the headline robust to the Magentic caveat?")
    R.line()
    e, h = key["wave2_median"], estimate(honest_median, k)
    same = (round(e.point, 6), round(e.lo, 6), round(e.hi, 6)) == \
           (round(h.point, 6), round(h.lo, 6), round(h.hi, 6))
    R.para("Yes, and the demonstration is exact. Rescoring the Magentic row on its honest "
           "flags-only surface (73.6% instead of 84.7%) and leaving the five standard "
           "rows untouched leaves the cross-framework median at {:.4f}% with the same "
           "CI {} — {}. AutoGen's pooled rate sits above the median under both "
           "readings, so the Magentic row never selects the median; it only sits above "
           "it. The published 55.0% headline therefore does not depend on the reading "
           "of the row that carries the most caveats."
           .format(h.point, interval(h),
                   "unchanged in every digit" if same else "SEE THE TABLE, IT MOVED"))

    # --- 6. widest -----------------------------------------------------------------
    R.line("## 6. The widest intervals in this file, stated up front")
    R.line()
    R.para("Wide intervals are the finding, not an embarrassment to bury. This table is "
           "derived from every interval this file publishes, not hand-picked: the {} "
           "widest of the {} intervals above.".format(8, len(R.tracked)))
    R.line("| quantity | point | 95% CI | width |")
    R.line("|---|---|---|---|")
    widest = sorted(R.tracked, key=lambda item: item[1].width, reverse=True)[:8]
    for label, e, sign in widest:
        R.line("| {} | {} | {} | {:.1f} pp |".format(
            label, pct(e.point, sign), interval(e, sign), e.width))
    R.line()
    R.para("The pattern is the honest one and it is worth saying plainly. The widest "
           "intervals in this file are (a) the framework-vs-framework comparisons, "
           "which is exactly why section 2 reports those rows as not distinguishable "
           "under this analysis, (b) anything computed on the {}-cell Magentic "
           "carve-out, the smallest row in the study, and (c) the O4 null contrast. A "
           "~{:.0f}-point-wide interval on the Magentic paired effect means the "
           "*direction* of that row's lift is solid and its *magnitude* is not pinned "
           "down better than \"very large\". Anyone quoting a Magentic lift to one "
           "decimal place is over-reading it. And an {:.0f}-point-wide interval around "
           "the O4 null is the reason section 4 refuses to call it equivalence."
           .format(total_n(t2, [MAGENTIC], clusters), widest[0][1].width,
                   key["o4_contrast"].width))

    # --- limitations ---------------------------------------------------------------
    R.line("## Limitations")
    R.line()
    limits = [
        "**Five clusters is few, and the intervals are correspondingly coarse.** Every "
        "CI here is read off a distribution with at most 126 support points, and "
        "several have far fewer — the `support` columns publish the exact number per "
        "statistic. A 2.5% tail on 126 points is about three points of weight. The "
        "replicate-jackknife range is published beside every interval for exactly this "
        "reason.",
        "**A sign test on {} replicates cannot reach p < 0.05.** The two-sided exact "
        "minimum is {:.4f}. Every per-replicate consistency statement in this file is "
        "descriptive."
        .format(k, sign_test_p(k, k)),
        "**The replicate labels are not random seeds, so nothing here is a seeded "
        "reproduction.** The values 11-15 never reached the pipeline model or any RNG "
        "(method, first paragraph). Re-running this study means re-running the matrix "
        "and drawing five fresh stochastic repetitions, not re-supplying a seed; the "
        "repetitions are not reproducible runs and these intervals do not claim they "
        "are. The clustering is justified by the shared cached baseline per "
        "(framework, config, task, replicate) group, which is a real design-induced "
        "dependence, not by any randomness the labels controlled.",
        "**Replicate-level resampling captures repetition-to-repetition variation only.** "
        "It "
        "cannot capture pipeline-model version drift, framework version drift, "
        "task-suite selection (5 tasks), or operator-suite selection (6 operators). "
        "Those are fixed constants of this design, not sampled populations. If the "
        "pipeline model is silently updated, none of these intervals covers that; the "
        "published version pins and the raw trace corpus are the defence there, not "
        "statistics.",
        "**The five standard scoreboard rows are not distinguishable under this "
        "analysis** (section 2). Sabot's cross-framework spread is not yet a ranking, "
        "and this file is the reason to stop reading it as one. Note the direction of "
        "that claim: failing to distinguish them is not the same as showing them "
        "equal. No equivalence margin was pre-declared anywhere in this project, so no "
        "null result here — not the row comparisons, not the O4 contrast — licenses an "
        "equivalence claim.",
        "**No multiplicity correction is applied.** This file reports {} intervals; at "
        "95% nominal coverage some would be expected to miss even under the null. The "
        "pre-registered headline is a single comparison (SPEC section 7) and is the "
        "confirmatory one; everything else here is descriptive."
        .format(len(R.tracked)),
        "**The paired grid is {} of {} valid wave-2 cells.** {} cells have no scored "
        "wave-1 partner (wave-2 O4 landing-probe exclusions and wave-1 BASELINE_FAIL "
        "exclusions), so the paired estimates run on a slightly smaller population "
        "than the published row rates. Both populations are stated in every table."
        .format(npair, n2, n2 - npair),
        "**The Magentic row's intervals do not launder its caveats.** " + CAVEAT_MAGENTIC,
        "**A cluster bootstrap on 5 clusters is known to under-cover.** The percentile "
        "interval is not calibrated to be exactly 95% at this cluster count, and no "
        "small-sample correction (BCa, t-adjustment) is applied — with 5 clusters the "
        "bias and acceleration terms would themselves be estimated from 5 points and "
        "would add false precision. Treat every interval here as an indicative width, "
        "not as a calibrated 95% guarantee.",
    ]
    for index, text in enumerate(limits, start=1):
        R.item(text, bullet="{}. ".format(index), indent="   ")
    R.line()
    return R.text(), key


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail if the recompute drifts from the frozen EXPECTED "
                             "table or from the committed UNCERTAINTY.md")
    args = parser.parse_args()

    text, key = render()
    actual = {name: (round(e.point, 4), round(e.lo, 4), round(e.hi, 4))
              for name, e in key.items() if name in EXPECTED}

    if args.check:
        drift = {n: (actual.get(n), v) for n, v in EXPECTED.items() if actual.get(n) != v}
        for name, (got, want) in sorted(drift.items()):
            print("DRIFT {}: recomputed {}, expected {}".format(name, got, want),
                  file=sys.stderr)
        stale = False
        if not OUT.exists():
            print("MISSING {} — run without --check to generate it".format(OUT),
                  file=sys.stderr)
            stale = True
        elif OUT.read_text() != text:
            stale = True
            print("DRIFT {} differs from the recompute:".format(OUT.name), file=sys.stderr)
            for line in list(difflib.unified_diff(
                    OUT.read_text().splitlines(), text.splitlines(),
                    fromfile="committed", tofile="recomputed", lineterm="", n=1))[:40]:
                print("  " + line, file=sys.stderr)
        if drift or stale:
            return 1
        print("uncertainty stable across {} pinned intervals; {} byte-identical".format(
            len(EXPECTED), OUT.name))
        return 0

    OUT.write_text(text)
    print("wrote {}".format(OUT))
    for name in ("wave1_median", "wave2_median", "median_contrast",
                 "paired_pooled_effect"):
        e = key[name]
        print("  {:24} {:+7.2f}  [{:+7.2f}, {:+7.2f}]".format(name, e.point, e.lo, e.hi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
