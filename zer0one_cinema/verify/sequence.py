"""Multi-frame gates + top-level frame-folder verification.

Gate C (motion coherence) needs 2 consecutive frames; uses OpenCV's
Farneback optical-flow. This is the only verify module that requires
`opencv-contrib-python` (installed via the `[preflight]` extra).

Also hosts the top-level `verify_frames()` entry that iterates a folder,
runs the selected gates, aggregates per-gate PASS-rates, and returns a
VerifyReport.

Filled in during Phase P3.
"""
from __future__ import annotations

from collections.abc import Iterable

from .report import GateResult, VerifyReport


def gate_motion(frame_a: object, frame_b: object) -> GateResult:
    raise NotImplementedError("phase P3")


def verify_frames(
    frames_dir: str,
    gates: Iterable[str] | None = None,
    reference_dir: str | None = None,
    strict: bool = False,
) -> VerifyReport:
    raise NotImplementedError("phase P3")
