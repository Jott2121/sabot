#!/usr/bin/env python
"""Wave-2 anomaly-first probe scorer — reads the probe out-dir and the frozen wave-1
matrix, writes PROBE-RESULTS.md into the probe out-dir. Any venv python works (pure
stdlib + sabot.probe).

Per probe cell it reports, side by side:
  - wave1_mapping: hard detection per the FROZEN wave-1 act mapping, on the probe run
    (from the probe cellverdict — the frozen score() path, untouched)
  - flags_anchored: the probe's new deterministic surface — a FLAGS line at/after the
    injection whose text contains a pre-registered anchor for the (task, operator)
  - union: either surface fired (the probe's headline "did detection lift" number)
  - flags_noticed: any non-'none' FLAGS line (diagnostic only, may flag non-fault noise)
and the matching wave-1 hard rate on the same (framework, config, task, operator) cells
from runs/matrix as the comparator."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.probe import scan_trace_flags

FRAMEWORKS = ("crewai", "autogen")
TASKS = ("T1", "T2", "T3", "T5")
OPERATORS = ("O1", "O3")
CONFIG = "guardrail"


def _cells(root: Path, framework: str, seeds: list[int]):
    for task in TASKS:
        for op in OPERATORS:
            for seed in seeds:
                yield task, op, seed, root / framework / CONFIG / task / op / f"seed{seed}"


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def collect(probe_root: Path, matrix_root: Path, framework: str, seeds: list[int]):
    rows = []
    for task, op, seed, cdir in _cells(probe_root, framework, seeds):
        verdict = _load(cdir / "cellverdict.json")
        if verdict is None:
            continue                       # not run (yet)
        row = {"framework": framework, "task": task, "operator": op, "seed": seed,
               "excluded": verdict["excluded"], "wave1_mapping": verdict["detected_hard"],
               "recovered": verdict["recovered"], "flags_noticed": False,
               "flags_anchored": False, "flags": []}
        rr = _load(cdir / "runresult.json")
        if rr is not None and row["excluded"] is None:
            scan = scan_trace_flags(rr["trace"], task, op, rr["injection_seq"] or 0)
            row.update(flags_noticed=scan["noticed"], flags_anchored=scan["anchored"],
                       flags=scan["flags"])
        wave1 = _load(matrix_root / framework / CONFIG / task / op / f"seed{seed}"
                      / "cellverdict.json")
        row["wave1_hard"] = None if wave1 is None or wave1["excluded"] else wave1["detected_hard"]
        row["wave1_excluded"] = None if wave1 is None else wave1["excluded"]
        rows.append(row)
    return rows


def _rate(hits: int, total: int) -> str:
    return f"{100 * hits / total:.1f}% ({hits}/{total})" if total else "n/a (0)"


def aggregate(rows, keyfn):
    groups: dict = {}
    for r in rows:
        if r["excluded"] is not None:
            continue
        g = groups.setdefault(keyfn(r), {"valid": 0, "wave1_mapping": 0, "flags_anchored": 0,
                                         "union": 0, "flags_noticed": 0,
                                         "wave1_valid": 0, "wave1_hard": 0})
        g["valid"] += 1
        g["wave1_mapping"] += r["wave1_mapping"]
        g["flags_anchored"] += r["flags_anchored"]
        g["union"] += (r["wave1_mapping"] or r["flags_anchored"])
        g["flags_noticed"] += r["flags_noticed"]
        if r["wave1_hard"] is not None:
            g["wave1_valid"] += 1
            g["wave1_hard"] += r["wave1_hard"]
    return groups


def render(rows) -> str:
    lines = ["# Anomaly-first probe — results (wave-2 hypothesis)", "",
             "Probe config: guardrail only, T1/T2/T3/T5 x O1/O3, wave-1 seeds. "
             "`wave1 hard` = the same cells in the frozen wave-1 matrix. `union` = "
             "wave-1 mapping OR anchored FLAGS line (the probe's lift measure).", ""]
    header = ("| framework | group | valid | wave1 hard (matrix) | wave1-mapping (probe run) "
              "| flags anchored | union | flags noticed (diag) |")
    rule = "|---|---|---|---|---|---|---|---|"
    for title, keyfn in (("by operator", lambda r: (r["framework"], r["operator"])),
                         ("by task x operator",
                          lambda r: (r["framework"], f"{r['task']}/{r['operator']}"))):
        lines += [f"## {title}", "", header, rule]
        groups = aggregate(rows, keyfn)
        for key in sorted(groups):
            g = groups[key]
            v = g["valid"]
            lines.append(
                f"| {key[0]} | {key[1]} | {v} | {_rate(g['wave1_hard'], g['wave1_valid'])} "
                f"| {_rate(g['wave1_mapping'], v)} | {_rate(g['flags_anchored'], v)} "
                f"| {_rate(g['union'], v)} | {_rate(g['flags_noticed'], v)} |")
        lines.append("")
    excluded = [r for r in rows if r["excluded"] is not None]
    lines += ["## Probe exclusions", ""]
    if excluded:
        lines += [f"- {r['framework']}/{CONFIG}/{r['task']}/{r['operator']}/seed{r['seed']}: "
                  f"{r['excluded']}" for r in excluded]
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--probe-dir", default="runs/probe-anomaly")
    p.add_argument("--matrix-dir", default="runs/matrix")
    p.add_argument("--seeds-file", required=True)
    a = p.parse_args(argv)
    seeds = json.loads(Path(a.seeds_file).read_text())["seeds"]
    rows = []
    for fw in FRAMEWORKS:
        rows.extend(collect(Path(a.probe_dir), Path(a.matrix_dir), fw, seeds))
    md = render(rows)
    out = Path(a.probe_dir) / "PROBE-RESULTS.md"
    out.write_text(md)
    (Path(a.probe_dir) / "probe-rows.json").write_text(json.dumps(rows, indent=1,
                                                                  sort_keys=True))
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
