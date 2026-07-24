#!/usr/bin/env python
"""Wave-2 scorer (SPEC v0.2.0 section 10.5) — reads the wave-2 out-dir and the frozen
wave-1 matrix, writes WAVE2-RESULTS.md + wave2-rows.json into the out-dir. Any venv
python works (pure stdlib + sabot.wave2).

Per cell, side by side:
  - wave1_mapping: hard detection per the FROZEN wave-1 act mapping, on the wave-2
    run (from the cellverdict — the frozen score() path, untouched)
  - flags_anchored: the v0.2 FLAGS surface (SPEC 10.3-10.4), from the recorded trace
  - union: either surface fired — THE WAVE-2 HEADLINE (SPEC 10.5)
  - flags_noticed: any non-'none' FLAGS line (diagnostic only)
  - reacted: derived per SPEC 10.7.4 — a corrective act at/after detection. Every
    wave-1 mapping act is corrective by the section-2 vocabulary; a FLAGS act is a
    report, not a correction, so reacted == wave1_mapping. A union-detected cell
    with reacted=False is notice-without-act ON THE NEW SURFACE.
and the matching wave-1 hard rate on the same paired cells from runs/matrix."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sabot.wave2 import is_carved_out, scan_trace_flags_v2

FRAMEWORKS = ("langgraph", "crewai", "autogen")
CONFIGS = ("default", "guardrail")
TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")


def _cells(root: Path, seeds: list[int]):
    for fw in FRAMEWORKS:
        for config in CONFIGS:
            for task in TASKS:
                for op in OPERATORS:
                    if is_carved_out(fw, config, op):
                        continue
                    for seed in seeds:
                        yield (fw, config, task, op, seed,
                               root / fw / config / task / op / f"seed{seed}")


def _load(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def collect(root: Path, matrix_root: Path, seeds: list[int]):
    rows = []
    for fw, config, task, op, seed, cdir in _cells(root, seeds):
        verdict = _load(cdir / "cellverdict.json")
        if verdict is None:
            continue                       # not run (yet)
        row = {"framework": fw, "config": config, "task": task, "operator": op,
               "seed": seed, "excluded": verdict["excluded"],
               "wave1_mapping": verdict["detected_hard"],
               "reacted": verdict["detected_hard"],
               "recovered": verdict["recovered"], "flags_noticed": False,
               "flags_anchored": False, "flags": []}
        rr = _load(cdir / "runresult.json")
        if rr is not None and row["excluded"] is None:
            scan = scan_trace_flags_v2(rr["trace"], task, op, rr["injection_seq"] or 0)
            row.update(flags_noticed=scan["noticed"], flags_anchored=scan["anchored"],
                       flags=scan["flags"])
        row["union"] = bool(row["wave1_mapping"] or row["flags_anchored"])
        wave1 = _load(matrix_root / fw / config / task / op / f"seed{seed}"
                      / "cellverdict.json")
        row["wave1_hard"] = (None if wave1 is None or wave1["excluded"]
                             else wave1["detected_hard"])
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
        g = groups.setdefault(keyfn(r), {
            "valid": 0, "wave1_mapping": 0, "flags_anchored": 0, "union": 0,
            "flags_noticed": 0, "reacted": 0, "recovered": 0,
            "wave1_valid": 0, "wave1_hard": 0})
        g["valid"] += 1
        for k in ("wave1_mapping", "flags_anchored", "union", "flags_noticed",
                  "reacted", "recovered"):
            g[k] += r[k]
        if r["wave1_hard"] is not None:
            g["wave1_valid"] += 1
            g["wave1_hard"] += r["wave1_hard"]
    return groups


def render(rows) -> str:
    lines = ["# Sabot — wave-2 scoreboard (SPEC v0.2.0)", "",
             "Headline = `union` (hard tier: frozen wave-1 mapping OR anchored FLAGS, "
             "SPEC 10.5). `wave1 hard` = the same paired cells in the frozen wave-1 "
             "matrix. `reacted` derives per SPEC 10.7.4 (a FLAGS act is a report, not "
             "a correction). Magentic carve-out cells (SPEC 10.6) are not part of the "
             "matrix. Published 2026-07-24 — read the QC footnotes at the foot of "
             "this file before quoting ANY number above.", "",
             "O4 pairing note: the O4 landing probe (SPEC 10.7.2) can exclude wave-2 "
             "O4 cells that wave 1 counted, so on O4 rows the `wave1 hard` and wave-2 "
             "denominators may diverge — a strict paired comparison must filter both "
             "waves to the wave-2-valid cells (per-cell data in wave2-rows.json).", ""]
    header = ("| group | valid | wave1 hard (matrix) | wave1-mapping (wave-2 run) "
              "| flags anchored | UNION | reacted | recovered | flags noticed (diag) |")
    rule = "|---|---|---|---|---|---|---|---|---|"
    for title, keyfn in (
            ("Scoreboard — by framework x config",
             lambda r: f"{r['framework']}/{r['config']}"),
            ("By operator", lambda r: f"{r['framework']}/{r['operator']}"),
            ("By task x operator (fault-in-view detail)",
             lambda r: f"{r['framework']}/{r['config']}/{r['task']}/{r['operator']}")):
        lines += [f"## {title}", "", header, rule]
        groups = aggregate(rows, keyfn)
        for key in sorted(groups):
            g = groups[key]
            v = g["valid"]
            lines.append(
                f"| {key} | {v} | {_rate(g['wave1_hard'], g['wave1_valid'])} "
                f"| {_rate(g['wave1_mapping'], v)} | {_rate(g['flags_anchored'], v)} "
                f"| {_rate(g['union'], v)} | {_rate(g['reacted'], v)} "
                f"| {_rate(g['recovered'], v)} | {_rate(g['flags_noticed'], v)} |")
        lines.append("")
    excluded = [r for r in rows if r["excluded"] is not None]
    lines += ["## Exclusion appendix", ""]
    if excluded:
        counts: dict = {}
        for r in excluded:
            k = (r["framework"], r["config"], r["task"], r["operator"], r["excluded"])
            counts[k] = counts.get(k, 0) + 1
        lines += ["| framework | config | task | operator | code | count |",
                  "|---|---|---|---|---|---|"]
        for k in sorted(counts):
            lines.append(f"| {k[0]} | {k[1]} | {k[2]} | {k[3]} | {k[4]} | {counts[k]} |")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wave2-dir", default="runs/wave2")
    p.add_argument("--matrix-dir", default="runs/matrix")
    p.add_argument("--seeds-file", required=True)
    a = p.parse_args(argv)
    seeds = json.loads(Path(a.seeds_file).read_text())["seeds"]
    rows = collect(Path(a.wave2_dir), Path(a.matrix_dir), seeds)
    md = render(rows)
    (Path(a.wave2_dir) / "WAVE2-RESULTS.md").write_text(md)
    (Path(a.wave2_dir) / "wave2-rows.json").write_text(
        json.dumps(rows, indent=1, sort_keys=True))
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
