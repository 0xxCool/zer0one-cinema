"""Deterministic fix-rule mapping: CheckResult + SceneState → SceneMutation.

Each failing check has exactly one fix rule with a closed-form formula
(no search, no random exploration). See docs/research/preflight-frame-qa.md
§3 for the derivations.

Pure Python + numpy — no bpy import, so unit-testable with plain dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass

from .report import CheckResult, SceneMutation


@dataclass(frozen=True)
class SceneState:
    """Snapshot of the tunable scene attributes at iteration start.

    Populated by bpy_adapters.snapshot_scene_state() before each fix.
    """

    cam_fov_x_rad: float
    cam_to_car_distance_m: float
    image_width: int
    image_height: int
    ground_current_scale: tuple[float, float, float]
    view_exposure_current: float
    dof_focus_object_name: str | None
    dof_fstop_current: float


def compute_fix(check: CheckResult, state: SceneState) -> SceneMutation | None:
    """Return the SceneMutation for the given failing check, or None if unfixable.

    Filled in during Phase P4.
    """
    raise NotImplementedError("phase P4")
