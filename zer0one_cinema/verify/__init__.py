"""zer0one-cinema verify — post-render CGVF gate check for finished frames.

Runs the 6-gate Cinema-Grade Verification Framework (Lighting / Material /
Motion / Composition / Atmosphere / Grading) against a folder of rendered
frames. Machine-readable JSON + human-readable Markdown output; exit
codes drive CI integration.

Public surface:
    from zer0one_cinema.verify import verify_frames, GateResult, VerifyReport
"""
from __future__ import annotations

from .report import GateResult, VerifyReport, VerifyStatus
from .sequence import verify_frames

__all__ = [
    "GateResult",
    "VerifyReport",
    "VerifyStatus",
    "verify_frames",
]
