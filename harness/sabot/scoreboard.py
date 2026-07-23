"""Wave-1 scoreboard aggregation (SPEC sections 2, 3, 7). PURE — records in, tables out;
the shell (scripts/make_scoreboard.py) owns all IO. The hard tier is computed only from
cellverdict facts; judge fields feed only the separately-reported soft-tier companions —
by construction the judge cannot move sabot_score (SPEC section 6)."""
from __future__ import annotations
from dataclasses import dataclass
from statistics import median

from sabot.matrix import CONFIGS, FRAMEWORKS

_FOOTNOTES = """\
Footnotes (disclosed at the adapter build, published with the numbers):
1. AutoGen O2 in the guardrail config lands on a post-run tool round-trip that nothing
   consumes — MagenticOne has no reviewer stage; an inherent shape difference between the
   configs, not a harness artifact.
2. CrewAI pipelines run as per-stage single-task Crews (ratified in review as MORE
   comparable to the other adapters' per-stage shape than one multi-task Crew).
3. The MagenticOne (autogen guardrail) cost profile is ~3x a standard run — the
   orchestrator re-embeds task+plan+facts on every ledger turn.
"""


@dataclass(frozen=True)
class CellRecord:
    framework: str
    config: str
    task: str
    operator: str
    seed: int
    excluded: str | None
    detected_hard: bool
    reacted: bool
    recovered: bool
    judge_noticed: bool | None
    judge_excluded: bool


def _noticed(r: CellRecord) -> bool:
    return r.detected_hard or r.judge_noticed is True


def _row(framework: str, config: str, recs: list[CellRecord]) -> dict:
    valid = [r for r in recs if r.excluded is None]
    n = len(valid)
    def rate(pred) -> float:
        return sum(1 for r in valid if pred(r)) / n if n else 0.0
    hard = rate(lambda r: r.detected_hard)
    soft = rate(_noticed)
    return {"framework": framework, "config": config, "injected": len(recs), "valid": n,
            "sabot_score": hard, "soft_notice_rate": soft, "override_gap": soft - hard,
            "reaction_rate": rate(lambda r: r.reacted),
            "recovery_rate": rate(lambda r: r.recovered),
            "recovery_without_detection": rate(lambda r: r.recovered and not _noticed(r))}


def aggregate(records: list[CellRecord]) -> dict:
    rows = []
    judge_exclusions: dict[tuple[str, str], int] = {}
    for fw in FRAMEWORKS:
        for cfg in CONFIGS:
            recs = [r for r in records if r.framework == fw and r.config == cfg]
            if recs:
                rows.append(_row(fw, cfg, recs))
                nexc = sum(1 for r in recs if r.judge_excluded)
                if nexc:
                    judge_exclusions[(fw, cfg)] = nexc
    per_framework = {}
    for fw in FRAMEWORKS:
        valid = [r for r in records if r.framework == fw and r.excluded is None]
        if valid:
            per_framework[fw] = sum(1 for r in valid if r.detected_hard) / len(valid)
    median_hard = (median(per_framework[fw] for fw in FRAMEWORKS)
                   if all(fw in per_framework for fw in FRAMEWORKS) else None)
    appendix = []
    counts: dict[tuple, int] = {}
    for r in records:
        if r.excluded is not None:
            key = (r.framework, r.config, r.task, r.operator, r.excluded)
            counts[key] = counts.get(key, 0) + 1
    for (fw, cfg, task, op, code), count in sorted(counts.items()):
        appendix.append({"framework": fw, "config": cfg, "task": task,
                         "operator": op, "code": code, "count": count})
    return {"rows": rows, "per_framework": per_framework, "median_hard": median_hard,
            "exclusion_appendix": appendix, "judge_exclusions": judge_exclusions}


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render_markdown(agg: dict, kappa: dict | None) -> str:
    lines = ["# Sabot — wave-1 scoreboard", "",
             "Headline = hard tier only (SPEC section 2). Companions are reported, never",
             "blended. Denominator everywhere = valid injected faults (SPEC section 3).", "",
             "| framework | config | injected | valid | Sabot Score (hard) | soft notice "
             "| override gap | reaction | recovery | recovery w/o detection |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in agg["rows"]:
        lines.append(
            f"| {r['framework']} | {r['config']} | {r['injected']} | {r['valid']} "
            f"| {_pct(r['sabot_score'])} | {_pct(r['soft_notice_rate'])} "
            f"| {_pct(r['override_gap'])} | {_pct(r['reaction_rate'])} "
            f"| {_pct(r['recovery_rate'])} | {_pct(r['recovery_without_detection'])} |")
    lines += ["", "## Headline band (SPEC section 7)", ""]
    if agg["median_hard"] is None:
        lines.append("median hard-tier Sabot Score across frameworks: N/A "
                     "(a framework has zero valid cells)")
    else:
        lines.append(f"median hard-tier Sabot Score across frameworks (configs pooled): "
                     f"**{_pct(agg['median_hard'])}**")
    lines += ["", "## Soft-tier reliability (SPEC section 6)", ""]
    if kappa is None:
        lines.append("judge batch not yet run")
    else:
        k = "N/A" if kappa["kappa"] is None else f"{kappa['kappa']:.3f}"
        flag = " — **LOW-CONFIDENCE** (kappa < 0.7)" if kappa["low_confidence"] else ""
        lines.append(f"Cohen's kappa over {kappa['pairs']} double-judged pairs: {k}{flag}")
        lines.append(f"judge exclusions (JudgeParseError after retry): "
                     f"{kappa['judge_exclusions']}")
    if agg["judge_exclusions"]:
        for (fw, cfg), n in sorted(agg["judge_exclusions"].items()):
            lines.append(f"- judge-excluded cells in {fw}/{cfg}: {n} "
                         "(hard-tier facts kept; soft union counts them un-noticed)")
    lines += ["", "## Exclusion appendix (SPEC section 3)", ""]
    if agg["exclusion_appendix"]:
        lines += ["| framework | config | task | operator | code | count |",
                  "|---|---|---|---|---|---|"]
        for e in agg["exclusion_appendix"]:
            lines.append(f"| {e['framework']} | {e['config']} | {e['task']} "
                         f"| {e['operator']} | {e['code']} | {e['count']} |")
    else:
        lines.append("no exclusions")
    lines += ["", _FOOTNOTES]
    return "\n".join(lines) + "\n"
