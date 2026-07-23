# tests/test_matrix.py
import pytest
from sabot.matrix import (CONFIGS, FRAMEWORKS, HARD_CAP_USD, OPERATORS, PER_RUN_USD,
                          TASKS, CellKey, run_profile, spent_usd)


def test_matrix_dimensions_match_spec_section_8():
    assert FRAMEWORKS == ("langgraph", "crewai", "autogen")
    assert CONFIGS == ("default", "guardrail")
    assert TASKS == ("T1", "T2", "T3", "T4", "T5")
    assert OPERATORS == ("O1", "O2", "O3", "O4", "O5", "O6")


def test_cellkey_relpath_faulted_and_baseline():
    k = CellKey(framework="crewai", config="guardrail", task="T3", operator="O2", seed=12)
    assert k.relpath() == "crewai/guardrail/T3/O2/seed12"
    b = CellKey(framework="crewai", config="guardrail", task="T3", operator=None, seed=12)
    assert b.relpath() == "crewai/guardrail/T3/baseline/seed12"


def test_run_profile_magentic_is_autogen_guardrail_only():
    assert run_profile("autogen", "guardrail") == "magentic"
    assert run_profile("autogen", "default") == "standard"
    assert run_profile("langgraph", "guardrail") == "standard"
    assert run_profile("crewai", "default") == "standard"


def test_spend_model_projects_and_caps():
    # Margined per-run constants: standard runs measured ~$0.012, magentic ~$0.05
    # (SPEND.md real token counts x published terra pricing); constants carry >=2x margin.
    assert PER_RUN_USD["standard"] >= 0.024
    assert PER_RUN_USD["magentic"] >= 0.10
    assert HARD_CAP_USD == 500.0
    usd = spent_usd({"standard": 875, "magentic": 175})
    assert 0 < usd < HARD_CAP_USD          # full wave-1 matrix projects UNDER the cap
    assert spent_usd({}) == 0.0
    with pytest.raises(KeyError):
        spent_usd({"unknown-profile": 1})   # fail loud, never guess a price
