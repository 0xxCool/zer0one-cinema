"""Dataclasses for verify — GateResult, VerifyReport, VerifyStatus.

Two output formats: JSON (machine-readable, sorted keys for determinism)
and Markdown (contact-sheet-style report for human review).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class VerifyStatus(str, Enum):
    """Gate outcome tri-state — used per gate and rolled up per frame."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class GateResult:
    """One gate's outcome on one frame."""

    name: str  # e.g. "A_lighting"
    status: VerifyStatus
    metrics: dict[str, float]  # measured values, keys documented in gates.py


@dataclass(frozen=True)
class FrameReport:
    """All gate results for a single frame."""

    frame_path: str
    gates: tuple[GateResult, ...]


@dataclass(frozen=True)
class VerifyReport:
    """Top-level report over N frames + optional Golden-Frame reference."""

    version: str
    frames: tuple[FrameReport, ...]
    overall: VerifyStatus  # worst status seen
    gate_pass_rate: dict[str, float] = field(default_factory=dict)  # per-gate PASS ratio
    reference_dir: str | None = None
