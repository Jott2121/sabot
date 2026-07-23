# tests/test_scoreboard.py
from sabot.scoreboard import _FOOTNOTES, CellRecord, aggregate, render_markdown


def _rec(**kw):
    base = dict(framework="langgraph", config="default", task="T1", operator="O1",
                seed=11, excluded=None, detected_hard=False, reacted=False,
                recovered=False, judge_noticed=None, judge_excluded=False)
    base.update(kw)
    return CellRecord(**base)


def test_row_rates_and_override_gap():
    recs = [
        _rec(detected_hard=True, reacted=True, recovered=True),          # hard
        _rec(operator="O2", judge_noticed=True),                          # soft only
        _rec(operator="O3", recovered=True, judge_noticed=False),         # lucky recovery
        _rec(operator="O4", judge_noticed=False),                         # missed
        _rec(operator="O5", excluded="RUN_ERROR"),                        # excluded
    ]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["injected"] == 5 and row["valid"] == 4
    assert row["sabot_score"] == 0.25
    assert row["soft_notice_rate"] == 0.5
    assert row["override_gap"] == 0.25
    assert row["reaction_rate"] == 0.25
    assert row["recovery_rate"] == 0.5
    assert row["recovery_without_detection"] == 0.25


def test_judge_excluded_counts_hard_only_and_is_reported():
    recs = [_rec(detected_hard=True, judge_excluded=True),
            _rec(operator="O2", judge_excluded=True)]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["sabot_score"] == 0.5 and row["soft_notice_rate"] == 0.5
    assert agg["judge_exclusions"][("langgraph", "default")] == 2


def test_median_hard_across_frameworks_pooled_configs():
    recs = ([_rec(detected_hard=True), _rec(config="guardrail")] +           # lg 0.5
            [_rec(framework="crewai"), _rec(framework="crewai", operator="O2")] +   # 0.0
            [_rec(framework="autogen", detected_hard=True),
             _rec(framework="autogen", operator="O2", detected_hard=True)])  # 1.0
    agg = aggregate(recs)
    assert agg["per_framework"] == {"langgraph": 0.5, "crewai": 0.0, "autogen": 1.0}
    assert agg["median_hard"] == 0.5


def test_exclusion_appendix_itemized_nonzero_only():
    recs = [_rec(excluded="BASELINE_FAIL"), _rec(seed=12, excluded="BASELINE_FAIL"),
            _rec(operator="O2", excluded="INJECTION_UNVERIFIED"), _rec(operator="O3")]
    agg = aggregate(recs)
    appendix = agg["exclusion_appendix"]
    assert {"framework": "langgraph", "config": "default", "task": "T1",
            "operator": "O1", "code": "BASELINE_FAIL", "count": 2} in appendix
    assert all(e["count"] > 0 for e in appendix) and len(appendix) == 2


def test_row_rate_denominator_zero_defaults_to_zero_not_one():
    # A group can be non-empty (injected > 0) with every record excluded (valid == 0).
    # The rate() closure's n==0 fallback must be 0.0, never 1.0 (that would silently
    # report a perfect score for a group with zero actually-scoreable cells).
    recs = [_rec(excluded="RUN_ERROR"), _rec(seed=12, excluded="BASELINE_FAIL")]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["injected"] == 2 and row["valid"] == 0
    assert row["sabot_score"] == 0.0
    assert row["soft_notice_rate"] == 0.0
    assert row["reaction_rate"] == 0.0
    assert row["recovery_rate"] == 0.0
    assert row["recovery_without_detection"] == 0.0


def test_recovery_without_detection_excludes_noticed_recoveries():
    # recovered AND noticed must NOT count toward recovery_without_detection.
    recs = [_rec(detected_hard=True, recovered=True)]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["recovery_rate"] == 1.0
    assert row["recovery_without_detection"] == 0.0


def test_aggregate_groups_records_by_framework_and_config_exactly():
    # framework and config must both match (AND, never OR) -- a record from a
    # different framework sharing the same config, or the same framework with a
    # different config, must not leak into an unrelated row's counts.
    recs = [_rec(), _rec(framework="crewai"), _rec(config="guardrail")]
    agg = aggregate(recs)
    row = next(r for r in agg["rows"]
              if r["framework"] == "langgraph" and r["config"] == "default")
    assert row["injected"] == 1 and row["valid"] == 1


def test_row_dict_carries_the_actual_framework_and_config_labels():
    recs = [_rec(framework="crewai", config="guardrail")]
    agg = aggregate(recs)
    row = agg["rows"][0]
    assert row["framework"] == "crewai"
    assert row["config"] == "guardrail"


def test_render_markdown_percent_formatting_is_exact_hundred_multiplier():
    recs = [_rec(detected_hard=True)]          # sabot_score == 1.0
    md = render_markdown(aggregate(recs), None)
    assert "100.0%" in md
    assert "101.0%" not in md                   # would appear under a x101 mutant


def test_render_markdown_full_featured_scenario_exact():
    recs = [
        _rec(detected_hard=True, reacted=True, recovered=True),
        _rec(seed=12, judge_noticed=False),
        _rec(framework="crewai", config="guardrail", operator="O2",
             detected_hard=True, judge_excluded=True),
        _rec(framework="autogen", operator="O3", detected_hard=True),
        _rec(framework="autogen", operator="O4", excluded="RUN_ERROR"),
    ]
    agg = aggregate(recs)
    kappa = {"pairs": 7, "kappa": 0.8123456, "low_confidence": False, "judge_exclusions": 2}
    md = render_markdown(agg, kappa)
    assert md == (
        "# Sabot — wave-1 scoreboard\n\n"
        "Headline = hard tier only (SPEC section 2). Companions are reported, never\n"
        "blended. Denominator everywhere = valid injected faults (SPEC section 3).\n\n"
        "| framework | config | injected | valid | Sabot Score (hard) | soft notice "
        "| override gap | reaction | recovery | recovery w/o detection |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| langgraph | default | 2 | 2 | 50.0% | 50.0% | 0.0% | 50.0% | 50.0% | 0.0% |\n"
        "| crewai | guardrail | 1 | 1 | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |\n"
        "| autogen | default | 2 | 1 | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% |\n\n"
        "## Headline band (SPEC section 7)\n\n"
        "median hard-tier Sabot Score across frameworks (configs pooled): **100.0%**\n\n"
        "## Soft-tier reliability (SPEC section 6)\n\n"
        "Cohen's kappa over 7 double-judged pairs: 0.812\n"
        "judge exclusions (JudgeParseError after retry): 2\n"
        "- judge-excluded cells in crewai/guardrail: 1 "
        "(hard-tier facts kept; soft union counts them un-noticed)\n\n"
        "## Exclusion appendix (SPEC section 3)\n\n"
        "| framework | config | task | operator | code | count |\n"
        "|---|---|---|---|---|---|\n"
        "| autogen | default | T1 | O4 | RUN_ERROR | 1 |\n\n"
        + _FOOTNOTES + "\n"
    )


def test_render_markdown_minimal_scenario_exact():
    recs = [_rec()]
    md = render_markdown(aggregate(recs), None)
    assert md == (
        "# Sabot — wave-1 scoreboard\n\n"
        "Headline = hard tier only (SPEC section 2). Companions are reported, never\n"
        "blended. Denominator everywhere = valid injected faults (SPEC section 3).\n\n"
        "| framework | config | injected | valid | Sabot Score (hard) | soft notice "
        "| override gap | reaction | recovery | recovery w/o detection |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| langgraph | default | 1 | 1 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |\n\n"
        "## Headline band (SPEC section 7)\n\n"
        "median hard-tier Sabot Score across frameworks: N/A "
        "(a framework has zero valid cells)\n\n"
        "## Soft-tier reliability (SPEC section 6)\n\n"
        "judge batch not yet run\n\n"
        "## Exclusion appendix (SPEC section 3)\n\n"
        "no exclusions\n\n"
        + _FOOTNOTES + "\n"
    )


def test_render_markdown_kappa_none_value_and_low_confidence_flag_exact():
    recs = [_rec()]
    kappa = {"pairs": 0, "kappa": None, "low_confidence": True, "judge_exclusions": 0}
    md = render_markdown(aggregate(recs), kappa)
    assert ("Cohen's kappa over 0 double-judged pairs: N/A "
            "— **LOW-CONFIDENCE** (kappa < 0.7)") in md
    assert "judge exclusions (JudgeParseError after retry): 0" in md


def test_render_markdown_carries_headline_kappa_and_footnotes():
    recs = [_rec(detected_hard=True), _rec(framework="crewai"),
            _rec(framework="autogen", config="guardrail")]
    md = render_markdown(aggregate(recs),
                         {"pairs": 3, "kappa": 0.55, "low_confidence": True,
                          "judge_exclusions": 1})
    assert "Sabot Score" in md and "LOW-CONFIDENCE" in md
    assert "MagenticOne has no reviewer stage" in md          # AutoGen O2 footnote
    assert "per-stage single-task Crews" in md                # CrewAI staging footnote
    assert "~3x" in md                                        # Magentic cost footnote
    assert "median" in md.lower()
