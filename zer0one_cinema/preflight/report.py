"""Dataclasses + exceptions for the preflight subsystem.

All frozen for determinism: two runs with the same inputs must produce
byte-identical JSON reports (compared via sha256 in the E2E suite).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class PreflightState(str, Enum):
    """Terminal states of the preflight loop."""

    PASS = "PASS"
    MAX_ITERS_EXCEEDED = "MAX_ITERS_EXCEEDED"
    STUCK = "STUCK"
    RENDER_FAILED = "RENDER_FAILED"
    NO_CAR_FOUND = "NO_CAR_FOUND"


CheckName = Literal[
    "car_fully_in_frame",
    "composition_rule_of_thirds",
    "ground_infinite",
    "sharpness_on_car_roi",
    "exposure_clipping",
]


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one analyzer check on one preview frame."""

    name: CheckName
    passed: bool
    magnitude: float  # absolute severity — used to pick the worst fail per iter
    details: dict[str, float]  # measured values (ndc offsets, laplacian var, …)


@dataclass(frozen=True)
class SceneMutation:
    """Delta to apply to the scene state before the next preview render.

    Every field is optional — a mutation may adjust only one aspect.
    """

    fix_class: str  # e.g. "cam_lateral_shift"
    cam_delta_local: tuple[float, float, float] | None = None  # meters, camera-local
    cam_rotation_delta_z_rad: float | None = None
    ground_scale_factor: float | None = None
    dof_focus_car: bool = False
    dof_min_fstop: float | None = None
    view_exposure_delta: float | None = None
    details: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class IterationLog:
    """Record of one preflight iteration."""

    iteration: int
    checks: tuple[CheckResult, ...]
    mutation: SceneMutation | None  # None on the final PASS iteration


@dataclass(frozen=True)
class PreflightReport:
    """Top-level report — written to disk as JSON, returned to CLI."""

    state: PreflightState
    version: str  # zer0one-cinema __version__
    seed: int
    camera_name: str
    iterations: tuple[IterationLog, ...]
    preview_frame_paths: tuple[str, ...]  # for contact-sheet review


class PreflightFailed(RuntimeError):
    """Raised by the loop when it terminates without PASS.

    The caller (CLI) catches this to translate into a non-zero exit code
    plus a written JSON report; library callers can inspect .report directly.
    """

    def __init__(self, report: PreflightReport) -> None:
        super().__init__(f"preflight failed: {report.state.value}")
        self.report = report
