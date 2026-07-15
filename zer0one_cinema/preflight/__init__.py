"""zer0one-cinema preflight — analyze one preview frame, auto-fix, verdict.

Runs before every full render to catch known bug classes (car cut off,
ground edge visible, center-locked composition, exposure clipping) on a
5-second EEVEE preview frame. Applies up to MAX_ITERS=3 deterministic
fixes; if the frame is still failing, aborts with a structured JSON
report — no GPU spend on a bug we can't fix.

Public surface:
    from zer0one_cinema.preflight import run_preflight, PreflightReport
"""
from __future__ import annotations

from .loop import run_preflight
from .report import (
    CheckResult,
    PreflightFailed,
    PreflightReport,
    PreflightState,
    SceneMutation,
)

__all__ = [
    "CheckResult",
    "PreflightFailed",
    "PreflightReport",
    "PreflightState",
    "SceneMutation",
    "run_preflight",
]
