"""Adapter protocol + cell scoring seam. The runner is deliberately thin: adapters
own all IO and framework contact; run_cell only turns two RunResults into a verdict.
The Phase-4 matrix driver owns looping, retries, and trace persistence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from sabot.score import CellVerdict, score
from sabot.trace import Trace


@dataclass(frozen=True)
class Cell:
    framework: str
    task: str
    config: str
    operator: str | None
    operator_spec: dict | None
    seed: int


@dataclass
class RunResult:
    trace: Trace
    task_passed: bool
    injection_seq: int | None
    injection_verified: bool
    error: str | None = None


class Adapter(Protocol):
    def run(self, cell: Cell) -> RunResult: ...


def run_cell(adapter: Adapter, cell: Cell, faulted: RunResult,
             baseline: RunResult) -> CellVerdict:
    run_error = faulted.error is not None or baseline.error is not None
    injection_verified = faulted.injection_verified and faulted.injection_seq is not None
    return score(trace=faulted.trace,
                 injection_seq=faulted.injection_seq or 0,
                 baseline_passed=baseline.task_passed,
                 task_passed=faulted.task_passed,
                 injection_verified=injection_verified,
                 run_error=run_error)
