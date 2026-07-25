"""Tests for the v0.2.1 replicate-cluster uncertainty estimator.

Vocabulary note: the data field is named `seed`, so the fixtures below use that key,
but it is a REPLICATE LABEL — it was never fed to the pipeline model or to any RNG
(see sabot/uncertainty.py). The only real RNG seed in play is MC_SEED, the analysis's
own, used for the Monte-Carlo cross-check.

Three jobs, in order of importance:

1. **Hand-checked micro-examples.** Every estimator is exercised on a dataset small
   enough to compute on paper, so the tests pin the ARITHMETIC and not just the shape.
   A k=2 cluster bootstrap has exactly three resamples with weights 1, 2, 1 — small
   enough that the whole bootstrap distribution is written out in the assertions.
2. **Determinism.** The published intervals come from exhaustive enumeration and must
   not depend on `MC_SEED` at all; the Monte-Carlo path must be byte-reproducible from
   its fixed RNG seed, and must agree with the exhaustive path.
3. **A regression pin of the real generated intervals.** `scripts/score_uncertainty.py`
   freezes its own EXPECTED table; this file asserts the script's recompute still
   matches it AND that the committed `runs/wave2/UNCERTAINTY.md` is byte-identical to a
   fresh render, so a silent drift in the data or the estimator is loud here as well as
   in CI's `--check`.
"""
import importlib.util
import pathlib

import pytest

from sabot.uncertainty import (MC_SEED, Estimate, cluster_ids, combine, contrast_stat,
                               diff_stat, distribution, estimate, exhaustive_resamples,
                               jackknife_values, median_stat, monte_carlo_resamples,
                               observed, per_cluster_values, rate_stat, sign_counts,
                               sign_test_p, tabulate, weighted_percentile)

ROOT = pathlib.Path(__file__).resolve().parent.parent

# A dataset small enough to check by hand. One group "a" over two replicates:
#   replicate 1: 1 hit of 2 cells   replicate 2: 2 hits of 2 cells   observed 3/4 = 75%
HAND_ROWS = [
    {"group": "a", "seed": 1, "hit": 1, "other": 0},
    {"group": "a", "seed": 1, "hit": 0, "other": 1},
    {"group": "a", "seed": 2, "hit": 1, "other": 1},
    {"group": "a", "seed": 2, "hit": 1, "other": 0},
]
HAND_METRICS = {"hit": lambda r: r["hit"], "other": lambda r: r["other"]}


@pytest.fixture()
def hand_table():
    return tabulate(HAND_ROWS, lambda r: r["group"], HAND_METRICS, (1, 2))


# --- resample enumeration --------------------------------------------------------------

def test_five_clusters_give_exactly_126_resamples_weighing_3125():
    """The discreteness claim the whole method rests on, asserted rather than asserted-in-prose."""
    items = list(exhaustive_resamples(5))
    assert len(items) == 126
    assert sum(weight for _, weight in items) == 5 ** 5 == 3125
    assert all(sum(counts) == 5 for counts, _ in items)
    assert len({counts for counts, _ in items}) == 126


def test_three_clusters_enumerate_by_hand():
    """C(5,2) = 10 multisets; the all-on-one draws have weight 1 and (1,1,1) weight 3! = 6."""
    items = dict(exhaustive_resamples(3))
    assert len(items) == 10
    assert sum(items.values()) == 27
    assert items[(3, 0, 0)] == 1
    assert items[(1, 1, 1)] == 6
    assert items[(2, 1, 0)] == 3


def test_one_cluster_is_the_degenerate_case():
    assert list(exhaustive_resamples(1)) == [((1,), 1)]


def test_zero_clusters_is_an_error_not_an_empty_bootstrap():
    with pytest.raises(ValueError):
        list(exhaustive_resamples(0))
    with pytest.raises(ValueError):
        list(monte_carlo_resamples(0))


def test_monte_carlo_is_reproducible_from_its_documented_seed():
    first = list(monte_carlo_resamples(5, replicates=50, seed=MC_SEED))
    second = list(monte_carlo_resamples(5, replicates=50, seed=MC_SEED))
    assert first == second
    assert len(first) == 50
    assert all(sum(counts) == 5 and weight == 1 for counts, weight in first)


def test_a_different_monte_carlo_seed_gives_a_different_stream():
    assert (list(monte_carlo_resamples(5, replicates=50, seed=MC_SEED))
            != list(monte_carlo_resamples(5, replicates=50, seed=MC_SEED + 1)))


def test_observed_resample_is_every_cluster_once():
    assert observed(5) == (1, 1, 1, 1, 1)


# --- percentiles -----------------------------------------------------------------------

FLAT = [(0.0, 1), (1.0, 1), (2.0, 1), (3.0, 1)]


@pytest.mark.parametrize("p,expected", [(0.0, 0.0), (0.25, 0.0), (0.26, 1.0),
                                        (0.5, 1.0), (0.75, 2.0), (1.0, 3.0)])
def test_type_1_percentile_on_a_flat_distribution(p, expected):
    """Smallest value whose cumulative weight reaches p of the total — no interpolation."""
    assert weighted_percentile(FLAT, p) == expected


def test_percentile_respects_the_weights():
    """The 97.5th of a distribution that is 99% mass at 0 is 0, not the max."""
    heavy = [(0.0, 99), (10.0, 1)]
    assert weighted_percentile(heavy, 0.975) == 0.0
    assert weighted_percentile(heavy, 0.999) == 10.0


def test_percentile_rejects_an_empty_distribution_and_out_of_range_p():
    with pytest.raises(ValueError):
        weighted_percentile([], 0.5)
    with pytest.raises(ValueError):
        weighted_percentile(FLAT, 1.5)
    with pytest.raises(ValueError):
        weighted_percentile(FLAT, -0.01)


# --- tabulate / combine ----------------------------------------------------------------

def test_tabulate_counts_cells_and_metrics_per_cluster(hand_table):
    assert hand_table == {"a": {1: {"n": 2, "hit": 1, "other": 1},
                                2: {"n": 2, "hit": 2, "other": 1}}}


def test_tabulate_drops_a_cell_whose_group_is_none():
    table = tabulate(HAND_ROWS, lambda r: None if r["seed"] == 2 else "a",
                     HAND_METRICS, (1, 2))
    assert table["a"][2] == {"n": 0, "hit": 0, "other": 0}
    assert sum(table["a"][c]["n"] for c in (1, 2)) == 2


def test_tabulate_refuses_a_cluster_it_was_not_told_about():
    with pytest.raises(KeyError):
        tabulate(HAND_ROWS, lambda r: "a", HAND_METRICS, (1,))


def test_combine_sums_with_multiplicity(hand_table):
    assert combine(hand_table, ["a"], (1, 1), (1, 2)) == {"n": 4, "hit": 3, "other": 2}
    assert combine(hand_table, ["a"], (2, 0), (1, 2)) == {"n": 4, "hit": 2, "other": 2}
    assert combine(hand_table, ["a"], (0, 2), (1, 2)) == {"n": 4, "hit": 4, "other": 2}


def test_cluster_ids_are_the_sorted_distinct_replicate_labels():
    assert cluster_ids(HAND_ROWS) == (1, 2)
    assert cluster_ids([{"cell": 7}, {"cell": 3}], cluster_key="cell") == (3, 7)


# --- statistics, computed by hand ------------------------------------------------------

def test_rate_stat_matches_hand_arithmetic(hand_table):
    stat = rate_stat(hand_table, ["a"], "hit", (1, 2))
    assert stat((1, 1)) == 75.0          # 3 of 4
    assert stat((2, 0)) == 50.0          # replicate 1 twice: 2 of 4
    assert stat((0, 2)) == 100.0         # replicate 2 twice: 4 of 4


def test_diff_stat_is_the_mean_per_cell_paired_difference(hand_table):
    stat = diff_stat(hand_table, ["a"], "hit", "other", (1, 2))
    assert stat((1, 1)) == 25.0          # (3 - 2) / 4
    assert stat((2, 0)) == 0.0           # (2 - 2) / 4
    assert stat((0, 2)) == 50.0          # (4 - 2) / 4


def test_median_stat_takes_the_median_under_the_same_resample():
    stat = median_stat([lambda w: 10.0, lambda w: 30.0, lambda w: 20.0])
    assert stat((1, 1)) == 20.0


def test_contrast_stat_subtracts_under_the_same_resample(hand_table):
    hit = rate_stat(hand_table, ["a"], "hit", (1, 2))
    other = rate_stat(hand_table, ["a"], "other", (1, 2))
    assert contrast_stat(hit, other)((1, 1)) == 25.0


def test_an_empty_resampled_group_is_nan_not_a_zero_rate():
    """A zero denominator must not silently become 0%: that would look like perfect
    non-detection rather than an absent measurement."""
    rows = [{"group": "a", "seed": 1, "hit": 1}]
    table = tabulate(rows, lambda r: "a", {"hit": lambda r: r["hit"]}, (1, 2))
    rate = rate_stat(table, ["a"], "hit", (1, 2))
    diff = diff_stat(table, ["a"], "hit", "hit", (1, 2))
    assert rate((0, 2)) != rate((0, 2))       # nan
    assert diff((0, 2)) != diff((0, 2))       # nan
    assert rate((1, 1)) == 100.0


# --- estimate: the whole pipeline, by hand ---------------------------------------------

def test_estimate_on_the_hand_dataset_is_fully_hand_checkable(hand_table):
    """k=2: resamples (2,0) w1 -> 50%, (1,1) w2 -> 75%, (0,2) w1 -> 100%; total weight 4.
    2.5th percentile threshold 0.1 -> 50.0; 97.5th threshold 3.9 -> 100.0.
    Jackknife: drop replicate 1 -> 100%, drop replicate 2 -> 50%."""
    e = estimate(rate_stat(hand_table, ["a"], "hit", (1, 2)), 2)
    assert isinstance(e, Estimate)
    assert e.point == 75.0
    assert (e.lo, e.hi) == (50.0, 100.0)
    assert (e.dist_min, e.dist_max) == (50.0, 100.0)
    assert e.support == 3
    assert (e.jack_lo, e.jack_hi) == (50.0, 100.0)
    assert e.width == 50.0


def test_distribution_carries_the_multinomial_weights(hand_table):
    dist = distribution(rate_stat(hand_table, ["a"], "hit", (1, 2)),
                        exhaustive_resamples(2))
    assert dist == [(50.0, 1), (75.0, 2), (100.0, 1)]


def test_jackknife_and_per_cluster_values_are_in_cluster_order(hand_table):
    stat = rate_stat(hand_table, ["a"], "hit", (1, 2))
    assert jackknife_values(stat, 2) == [100.0, 50.0]   # drop replicate 1, then 2
    assert per_cluster_values(stat, 2) == [50.0, 100.0]  # replicate 1, then 2, alone


def test_a_wider_alpha_gives_a_narrower_interval(hand_table):
    stat = rate_stat(hand_table, ["a"], "hit", (1, 2))
    wide = estimate(stat, 2, alpha=0.05)
    narrow = estimate(stat, 2, alpha=0.5)
    assert narrow.width <= wide.width


def test_monte_carlo_agrees_with_the_exhaustive_enumeration(hand_table):
    """The MC path is a cross-check, so it has to land on the same answer."""
    stat = rate_stat(hand_table, ["a"], "hit", (1, 2))
    exact = estimate(stat, 2)
    mc = estimate(stat, 2, resamples=monte_carlo_resamples(2, replicates=5000))
    assert mc.point == exact.point
    assert abs(mc.lo - exact.lo) < 1e-9 and abs(mc.hi - exact.hi) < 1e-9


# --- the sign test and its ceiling -----------------------------------------------------

def test_sign_counts_splits_positive_negative_and_zero():
    assert sign_counts([1.0, -2.0, 0.0, 3.0]) == (2, 1, 1)
    assert sign_counts([]) == (0, 0, 0)


@pytest.mark.parametrize("positive,n,expected", [
    (5, 5, 2 / 32), (0, 5, 2 / 32), (4, 5, 12 / 32), (1, 5, 12 / 32),
    (3, 5, 1.0), (2, 5, 1.0), (1, 1, 1.0), (0, 0, 1.0),
])
def test_exact_two_sided_sign_test_p_values(positive, n, expected):
    assert sign_test_p(positive, n) == pytest.approx(expected)


def test_five_replicates_can_never_reach_the_conventional_threshold():
    """The limitation the report states in prose, pinned as arithmetic: even a perfect
    5/5 split is p = 0.0625 > 0.05."""
    assert sign_test_p(5, 5) > 0.05
    assert min(sign_test_p(i, 5) for i in range(6)) == pytest.approx(0.0625)


def test_sign_test_rejects_impossible_counts():
    with pytest.raises(ValueError):
        sign_test_p(6, 5)
    with pytest.raises(ValueError):
        sign_test_p(-1, 5)


# --- regression pin against the real published data ------------------------------------

def _load_script():
    path = ROOT / "scripts" / "score_uncertainty.py"
    spec = importlib.util.spec_from_file_location("score_uncertainty", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rendered():
    script = _load_script()
    if not script.ROWS.exists() or not script.MATRIX.exists():
        pytest.skip("wave-2 rows / wave-1 matrix not available in this checkout")
    text, key = script.render()
    return script, text, key


def test_the_published_intervals_have_not_drifted(rendered):
    """The regression pin: every interval frozen in the script's EXPECTED table must come
    back to 4 decimal places. This is the same gate CI runs as `--check`."""
    script, _, key = rendered
    actual = {name: (round(e.point, 4), round(e.lo, 4), round(e.hi, 4))
              for name, e in key.items() if name in script.EXPECTED}
    assert actual == script.EXPECTED


def test_the_committed_markdown_is_byte_identical_to_a_fresh_render(rendered):
    script, text, _ = rendered
    assert script.OUT.exists(), "runs/wave2/UNCERTAINTY.md is not committed"
    assert script.OUT.read_text() == text


def test_the_headline_point_estimates_still_reproduce_what_is_published(rendered):
    """No published number may move. 16.7% -> 55.0% must survive verbatim."""
    _, _, key = rendered
    assert round(key["wave1_median"].point, 1) == 16.7
    assert round(key["wave2_median"].point, 1) == 55.0
    assert round(key["union/autogen/guardrail"].point, 1) == 84.7
    assert round(key["magentic_flags_only"].point, 1) == 73.6
    assert round(key["o4_honest_mapping_only"].point, 1) == 9.8
    assert round(key["rwd_union"].point, 1) == 26.1
    assert round(key["rwd_frozen"].point, 1) == 50.0


def test_every_published_point_estimate_lies_inside_its_own_interval(rendered):
    _, _, key = rendered
    for name, e in key.items():
        assert e.lo <= e.point <= e.hi, name
        assert e.dist_min <= e.lo and e.hi <= e.dist_max, name
        assert e.support <= 126, name


def test_the_headline_lift_interval_excludes_zero(rendered):
    """The substantive claim the reviewer asked to see interval-tested."""
    _, _, key = rendered
    assert key["median_contrast"].lo > 0
    assert key["paired_pooled_effect"].lo > 0


def test_the_o4_null_is_published_as_a_contrast_that_straddles_zero(rendered):
    """The O4 claim must be ONE contrast with an interval, not two overlapping
    intervals: overlap is neither necessary nor sufficient for a null."""
    _, _, key = rendered
    for name in ("o4_contrast", "o4_matched_contrast"):
        e = key[name]
        assert e.lo < 0 < e.hi, name
    # And the direction is not even stable across the two denominator choices, which is
    # the strongest honest statement available about this surface.
    assert key["o4_contrast"].point < 0 < key["o4_matched_contrast"].point


def test_the_o4_contrast_is_the_difference_of_the_two_published_o4_rates(rendered):
    """The as-published contrast must be exactly 24.5% - 26.0%, so a reader checking it
    against the README's two numbers lands on the same place."""
    _, _, key = rendered
    expected = key["o4_fault_anchored"].point - key["o4_clean_base"].point
    assert key["o4_contrast"].point == pytest.approx(expected)


def _unwrapped(text):
    """The report is hard-wrapped at 79 columns, so phrase assertions run against a
    whitespace-collapsed copy rather than accidentally testing the line breaks."""
    return " ".join(text.split())


def test_the_report_refuses_to_claim_equivalence_from_a_null(rendered):
    """A null contrast without a pre-declared equivalence margin is not equivalence, and
    the report has to say so rather than let a reader infer it."""
    _, text, _ = rendered
    flat = _unwrapped(text)
    assert "A null contrast is not equivalence." in flat
    assert "no equivalence margin was pre-declared" in flat
    assert "statistically indistinguishable" not in flat
    assert "not distinguishable under this analysis" in flat


def test_the_report_calls_the_labels_replicates_not_random_seeds(rendered):
    """The replicate labels were never fed to the model or an RNG; the report must not
    grant them a randomness they do not have."""
    _, text, _ = rendered
    flat = _unwrapped(text)
    assert "is a replicate label, not a random seed" in flat
    assert "never passed to the pipeline model and never passed to any RNG" in flat
    assert "replicate-cluster bootstrap" in flat
    assert "seed-paired" not in flat and "seed-cluster" not in flat


def test_the_strict_floor_stays_below_the_published_union_on_every_row(rendered):
    """The README's floor/union pairing must hold at the point estimate on every row."""
    _, _, key = rendered
    for row in ("langgraph/default", "langgraph/guardrail", "crewai/default",
                "crewai/guardrail", "autogen/default", "autogen/guardrail"):
        assert key["strict/" + row].point <= key["union/" + row].point, row
