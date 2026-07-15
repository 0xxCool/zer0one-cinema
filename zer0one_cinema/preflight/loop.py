"""Preflight state-machine loop.

Iterates render → analyze → pick-worst-fail → apply-fix, up to MAX_ITERS
times. Terminates with one of PreflightState values. Emits a full
PreflightReport for every terminal state (PASS or failure).

MAX_ITERS=3 is empirically justified — Restore-Assess-Repeat literature
(arXiv 2603.26385, 2507.05598) shows iteration 4+ typically brings
diminishing returns or regression.
"""
from __future__ import annotations

from .bpy_adapters import PreflightAdapter
from .report import PreflightReport

MAX_ITERS_DEFAULT = 3


def run_preflight(
    adapter: PreflightAdapter,
    camera_name: str,
    output_dir: str,
    max_iters: int = MAX_ITERS_DEFAULT,
    seed: int = 0,
) -> PreflightReport:
    """Run the render-analyze-fix loop and return a terminal PreflightReport.

    Filled in during Phase P5.
    """
    raise NotImplementedError("phase P5")
