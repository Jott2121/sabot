"""SPEC v0.2.1 companion — statistical uncertainty for the published wave-2 numbers.

Every number Sabot has published so far is a point estimate. The scoreboard's unit of
observation is a CELL (framework x config x task x operator x replicate), and cells are
not independent, so a naive binomial interval over 786 cells would be far too narrow —
it would treat 786 correlated observations as 786 independent ones.

WHAT THE FIELD NAMED `seed` ACTUALLY IS
---------------------------------------
The data carries a field called `seed` with the values 11-15, and the word invites a
reading this design does not support. Those values were **never passed to the pipeline
model and never passed to any RNG**. Every adapter constructs its client from a model id
alone — `ChatOpenAI(model=model_id)`, `LLM(model=f"openai/{model_id}")`,
`OpenAIChatCompletionClient(model=model_id)` — with no `seed` and no `temperature`
kwarg, and `Cell.seed` reaches only run-id strings, recorder metadata and output paths.
The pre-registered seeds file says as much in its own rule text: "Seeds are repetition
identifiers recorded per run."

So 11-15 are **replicate labels on five stochastic repetitions**, not controlled random
seeds, and this module's vocabulary says so: replicate, replicate-cluster bootstrap,
replicate-jackknife. What is being run is a five-replicate design — a five-matrix
sensitivity analysis — and its intervals describe how much the answer moves across five
independent repetitions of the whole matrix. They do not describe a seeded, reproducible
random process, because there is not one.

WHY CLUSTER ON THE REPLICATE ANYWAY
-----------------------------------
The clustering is still the right choice, but its justification is structural rather than
stochastic. `scripts/run_matrix.py` caches one no-fault baseline run per
(framework, config, task, replicate) group and reuses it for all of that group's
operator cells: the exclusion decision, the `recovered` comparison and the clean-run
comparator of up to six cells all descend from a single shared run. That is a real
dependence structure induced by the design, it is aligned exactly with the replicate
label, and resampling whole replicates preserves it. The clustering is not arbitrary —
it is the shared baseline, not model-level randomness, that earns it.

Five clusters is a small number and this module refuses to hide that:

* A size-5 resample with replacement has only ``C(9,4) = 126`` distinct multisets
  (``5**5 = 3125`` ordered draws). The bootstrap distribution of any statistic is
  therefore DISCRETE and coarse, and a 2.5/97.5 percentile is being read off a
  distribution with at most 126 support points. `exhaustive_resamples` enumerates all
  126 with their exact multinomial weights, so the published percentile CIs carry **zero
  Monte-Carlo error** — they are the exact bootstrap percentiles, not a simulation of
  them. `monte_carlo_resamples` (fixed documented seed, `MC_SEED` — this one IS a real
  RNG seed, the module's own) exists only as an independent cross-check that the
  exhaustive path is right.
* Because the tails are coarse, every interval is published alongside a
  **replicate-jackknife leave-one-out range** (`jackknife_values`): the exact min and max
  of the statistic over the five "drop one replicate" datasets. That is a companion, not
  a rival — it answers "how much does one replicate move this?", which a percentile
  cannot.
* A sign test over 5 replicates cannot reach p < 0.05 in either direction: the smallest
  attainable two-sided p is ``2 / 2**5 = 0.0625`` (`sign_test_p(5, 5)`). Any per-replicate
  consistency claim here is descriptive, and this module makes that arithmetic explicit
  rather than letting a reader assume significance.

What replicate-level resampling CANNOT capture is stated in UNCERTAINTY.md's limitations
and repeated here because it is the honest boundary of the method: it captures
repetition-to-repetition variation at fixed everything-else. It does not capture
pipeline-model version drift, framework version drift, task-suite selection, or
operator-suite selection — those are fixed constants of this design, not sampled
populations, and no resampling of five replicates can put an interval on them.

Pure logic, standard library only, no file I/O, no third-party dependency (Python 3.9+),
matching `sabot/strict.py`. `scripts/score_uncertainty.py` supplies the data.
"""
from __future__ import annotations

import itertools
import math
import random
import statistics
from typing import Callable, Dict, Iterable, Iterator, List, NamedTuple, Optional, Sequence, Tuple

# Fixed, documented seed for the Monte-Carlo cross-check path. The PUBLISHED intervals do
# not depend on it: they come from `exhaustive_resamples`, which enumerates the entire
# bootstrap distribution. Changing this constant must not move a published number.
MC_SEED = 20260724
MC_REPLICATES = 20000

# A resample is a vector of cluster multiplicities, one entry per cluster, summing to the
# number of clusters. (1, 1, 1, 1, 1) is the observed dataset.
Resample = Tuple[int, ...]
Weighted = Tuple[Resample, int]
Counts = Dict[str, int]
Table = Dict[str, Dict[int, Counts]]
Stat = Callable[[Resample], float]


class Estimate(NamedTuple):
    """One published number with its replicate-cluster uncertainty.

    point       the statistic on the observed data (the published point estimate)
    lo, hi      exact bootstrap percentile CI at `alpha` (default 2.5 / 97.5)
    dist_min    smallest value any resample can produce (all 5 draws on one replicate)
    dist_max    largest value any resample can produce
    support     number of DISTINCT values in the bootstrap distribution (<= 126 for k=5)
    jack_lo     min over the 5 leave-one-replicate-out datasets
    jack_hi     max over the 5 leave-one-replicate-out datasets
    """

    point: float
    lo: float
    hi: float
    dist_min: float
    dist_max: float
    support: int
    jack_lo: float
    jack_hi: float

    @property
    def width(self) -> float:
        """CI width in the statistic's own units (percentage points, for every rate here)."""
        return self.hi - self.lo


# --- building the per-cluster sufficient statistics ------------------------------------

def cluster_ids(rows: Sequence[dict], cluster_key: str = "seed") -> Tuple[int, ...]:
    """The sorted distinct cluster ids present in `rows`. These ARE the bootstrap units.

    `cluster_key` defaults to `"seed"` because that is the field name in the published
    data; read it as the REPLICATE label (module docstring: it was never fed to a model
    or an RNG).
    """
    return tuple(sorted({r[cluster_key] for r in rows}))


def tabulate(rows: Sequence[dict],
             group_of: Callable[[dict], Optional[str]],
             metrics: Dict[str, Callable[[dict], int]],
             clusters: Sequence[int],
             cluster_key: str = "seed") -> Table:
    """Reduce cells to per-(group, cluster) integer counts.

    This is the whole point of the abstraction: once a dataset is reduced to counts per
    (group, replicate), a cluster bootstrap is exact integer arithmetic over 126 weight
    vectors, with no need to materialise a resampled cell list. `metrics` values must
    return 0/1 per cell; every group additionally carries `"n"`, the cell count.

    A `group_of` returning None drops the cell (used to restrict to the paired subset).
    """
    names = ["n"] + list(metrics)
    table: Table = {}
    for row in rows:
        group = group_of(row)
        if group is None:
            continue
        cluster = row[cluster_key]
        if cluster not in clusters:
            raise KeyError(f"row carries cluster {cluster!r}, not in {tuple(clusters)!r}")
        per = table.setdefault(group, {c: dict.fromkeys(names, 0) for c in clusters})
        per[cluster]["n"] += 1
        for name, fn in metrics.items():
            per[cluster][name] += int(fn(row))
    return table


def combine(table: Table, groups: Sequence[str], resample: Resample,
            clusters: Sequence[int]) -> Counts:
    """Total counts for `groups` under a resample, i.e. pooling with multiplicity."""
    total: Counts = {}
    for group in groups:
        per = table[group]
        for index, cluster in enumerate(clusters):
            weight = resample[index]
            if not weight:
                continue
            for name, value in per[cluster].items():
                total[name] = total.get(name, 0) + weight * value
    return total


# --- statistics, each a function of a resample -----------------------------------------

def rate_stat(table: Table, groups: Sequence[str], metric: str,
              clusters: Sequence[int]) -> Stat:
    """Percentage rate of `metric` pooled over `groups` (cell-weighted, as published)."""
    def stat(resample: Resample) -> float:
        total = combine(table, groups, resample, clusters)
        return 100.0 * total[metric] / total["n"] if total["n"] else float("nan")
    return stat


def diff_stat(table: Table, groups: Sequence[str], minuend: str, subtrahend: str,
              clusters: Sequence[int]) -> Stat:
    """Paired per-cell effect in percentage points: rate(minuend) - rate(subtrahend).

    Both metrics are counted over the SAME cells, so this is the mean of the per-cell
    paired difference — the reviewer's paired estimand, not a difference of two
    independently-scoped rates.
    """
    def stat(resample: Resample) -> float:
        total = combine(table, groups, resample, clusters)
        if not total["n"]:
            return float("nan")
        return 100.0 * (total[minuend] - total[subtrahend]) / total["n"]
    return stat


def median_stat(parts: Sequence[Stat]) -> Stat:
    """The cross-framework median — Sabot's headline aggregator (SPEC section 7).

    The same resample feeds every part, so the median is recomputed coherently rather
    than assembled from independently resampled pieces.
    """
    def stat(resample: Resample) -> float:
        return statistics.median([p(resample) for p in parts])
    return stat


def contrast_stat(left: Stat, right: Stat) -> Stat:
    """left - right under the same resample, so a two-arm contrast is drawn coherently
    rather than from two independent bootstraps.

    Used for the wave-1-vs-wave-2 headline and for the O4 fault-vs-clean-baseline null.
    On the cross-wave use: wave 2 reuses wave 1's registered replicate labels verbatim
    (seeds/wave2.json), so evaluating both waves on one drawn label multiset keeps the
    contrast replicate-matched. Matching by LABEL is an arbitrary but unbiased 1:1
    matching of repetitions — repetition 13 of a cell in wave 1 has no special affinity
    with repetition 13 of the same cell in wave 2, since the labels drove nothing. What
    carries the paired-difference estimate is matching by CELL; the label match only
    fixes which of the five repetitions pairs with which, and any other 1:1 assignment
    would be equally valid in expectation.
    """
    def stat(resample: Resample) -> float:
        return left(resample) - right(resample)
    return stat


# --- resampling ------------------------------------------------------------------------

def exhaustive_resamples(k: int) -> Iterator[Weighted]:
    """Every distinct size-k-with-replacement resample of k clusters, with its exact
    multinomial weight. Yields C(2k-1, k-1) items whose weights sum to k**k — for k=5,
    126 items summing to 3125. This is the entire bootstrap distribution, so percentiles
    computed from it have no Monte-Carlo error."""
    if k < 1:
        raise ValueError("need at least one cluster")
    factorials = [math.factorial(i) for i in range(k + 1)]
    for combo in itertools.combinations_with_replacement(range(k), k):
        counts = [0] * k
        for index in combo:
            counts[index] += 1
        weight = factorials[k]
        for count in counts:
            weight //= factorials[count]
        yield tuple(counts), weight


def monte_carlo_resamples(k: int, replicates: int = MC_REPLICATES,
                          seed: int = MC_SEED) -> Iterator[Weighted]:
    """Ordinary Monte-Carlo cluster bootstrap, fixed RNG seed, each draw weight 1.

    Kept as an independent cross-check of `exhaustive_resamples`, never as the source of
    a published interval. Uses `random.Random(seed).randrange`, whose stream is stable
    across CPython 3.9-3.13, so the cross-check is reproducible on every version CI runs.
    """
    if k < 1:
        raise ValueError("need at least one cluster")
    rng = random.Random(seed)
    for _ in range(replicates):
        counts = [0] * k
        for _ in range(k):
            counts[rng.randrange(k)] += 1
        yield tuple(counts), 1


def distribution(stat: Stat, resamples: Iterable[Weighted]) -> List[Tuple[float, int]]:
    """The statistic's weighted bootstrap distribution, sorted ascending by value."""
    accumulated: Dict[float, int] = {}
    for resample, weight in resamples:
        value = stat(resample)
        accumulated[value] = accumulated.get(value, 0) + weight
    return sorted(accumulated.items())


def weighted_percentile(dist: Sequence[Tuple[float, int]], p: float) -> float:
    """Type-1 (inverse-CDF) percentile of a weighted discrete distribution: the smallest
    value whose cumulative weight reaches p of the total.

    Chosen deliberately over an interpolating definition. With at most 126 support points
    there is nothing to interpolate honestly — an interpolated tail would invent
    resolution the design does not have. This returns a value the bootstrap actually
    produced.
    """
    if not dist:
        raise ValueError("empty distribution")
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p}")
    total = sum(weight for _, weight in dist)
    threshold = p * total
    cumulative = 0
    for value, weight in dist[:-1]:
        cumulative += weight
        if cumulative >= threshold - 1e-9:
            return value
    return dist[-1][0]


def observed(k: int) -> Resample:
    """The resample that reproduces the observed dataset: every cluster exactly once."""
    return tuple([1] * k)


def jackknife_values(stat: Stat, k: int) -> List[float]:
    """The statistic on each of the k leave-one-cluster-out datasets, in cluster order.

    Reported as an exact min/max companion to the percentile CI. With k=5 the percentile
    tails are read off a 126-point lattice; the jackknife range asks a different and
    fully exact question — how far does dropping any single replicate move the number?
    """
    values = []
    for i in range(k):
        weights = [1] * k
        weights[i] = 0
        values.append(stat(tuple(weights)))
    return values


def per_cluster_values(stat: Stat, k: int) -> List[float]:
    """The statistic computed within each single cluster alone, in cluster order.

    These are the per-replicate values a sign test counts over.
    """
    values = []
    for i in range(k):
        weights = [0] * k
        weights[i] = 1
        values.append(stat(tuple(weights)))
    return values


def estimate(stat: Stat, k: int, resamples: Optional[Iterable[Weighted]] = None,
             alpha: float = 0.05) -> Estimate:
    """Point estimate + exact cluster-bootstrap percentile CI + jackknife range."""
    dist = distribution(stat, exhaustive_resamples(k) if resamples is None else resamples)
    jack = jackknife_values(stat, k)
    return Estimate(point=stat(observed(k)),
                    lo=weighted_percentile(dist, alpha / 2.0),
                    hi=weighted_percentile(dist, 1.0 - alpha / 2.0),
                    dist_min=dist[0][0], dist_max=dist[-1][0], support=len(dist),
                    jack_lo=min(jack), jack_hi=max(jack))


# --- the sign test, and its ceiling ----------------------------------------------------

def sign_counts(values: Sequence[float]) -> Tuple[int, int, int]:
    """(positive, negative, zero) counts of per-replicate effects."""
    positive = sum(1 for v in values if v > 0)
    negative = sum(1 for v in values if v < 0)
    return positive, negative, len(values) - positive - negative


def sign_test_p(positive: int, n: int) -> float:
    """Exact two-sided sign-test p-value, ties counted as trials.

    Published mainly to make its own ceiling visible: with n=5 the most extreme possible
    outcome (5/5) gives 2/32 = 0.0625, so NO sign test on five replicates can reach the
    conventional 0.05. Per-replicate consistency here is a description of direction, never a
    significance claim.
    """
    if n < 0 or not 0 <= positive <= n:
        raise ValueError(f"positive={positive} out of range for n={n}")
    if n == 0:
        return 1.0
    extreme = max(positive, n - positive)
    tail = sum(math.comb(n, i) for i in range(extreme, n + 1))
    return min(1.0, 2.0 * tail / (2 ** n))


__all__ = ["MC_SEED", "MC_REPLICATES", "Estimate", "cluster_ids", "tabulate", "combine",
           "rate_stat", "diff_stat", "median_stat", "contrast_stat",
           "exhaustive_resamples", "monte_carlo_resamples", "distribution",
           "weighted_percentile", "observed", "jackknife_values", "per_cluster_values",
           "estimate", "sign_counts", "sign_test_p"]
