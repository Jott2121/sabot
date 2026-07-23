"""Phase-4 matrix bookkeeping. PURE — no IO, no framework imports, no adapters — so the
spend/cap logic that guards real money can be unit-tested and mutation-hardened before a
single paid call. The driver shell (scripts/run_matrix.py) owns all IO.

Spend model: run-count x margined per-run constants derived from SPEND.md's real
reconstructed token counts (2026-07-22 pilot + smokes) x the published gpt-5.6-terra
pricing ($2.50/$15.00 per 1M, SPEC section 8). Constants carry >=2x margin for revise
loops and retries. These are PROJECTION dollars for the cap circuit-breaker; the OpenAI
usage dashboard is the billing truth (same caveat as SPEND.md)."""
from __future__ import annotations
from dataclasses import dataclass

FRAMEWORKS = ("langgraph", "crewai", "autogen")
CONFIGS = ("default", "guardrail")
TASKS = ("T1", "T2", "T3", "T4", "T5")
OPERATORS = ("O1", "O2", "O3", "O4", "O5", "O6")

HARD_CAP_USD = 500.0

# standard: ~3,000 in + ~300 out tokens/run measured => ~$0.012; margined to $0.025.
# magentic: ~8,000 in + ~2,000 out tokens/run measured => ~$0.05; margined to $0.105.
PER_RUN_USD = {"standard": 0.025, "magentic": 0.105}


@dataclass(frozen=True)
class CellKey:
    framework: str
    config: str
    task: str
    operator: str | None
    seed: int

    def relpath(self) -> str:
        op = self.operator if self.operator is not None else "baseline"
        return f"{self.framework}/{self.config}/{self.task}/{op}/seed{self.seed}"


def run_profile(framework: str, config: str) -> str:
    """MagenticOneGroupChat (autogen guardrail config) re-embeds task+plan+facts on every
    orchestrator ledger turn — measured ~3x a standard run (SPEND.md Task 8 smoke)."""
    return "magentic" if (framework == "autogen" and config == "guardrail") else "standard"


def spent_usd(counts: dict[str, int]) -> float:
    return sum(PER_RUN_USD[profile] * n for profile, n in counts.items())
