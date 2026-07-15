"""Deterministic fix-rule mapping: CheckResult + SceneState → SceneMutation.

Each failing check has exactly one fix rule with a closed-form formula
(no search, no random exploration). See docs/research/preflight-frame-qa.md
§3 for the derivations.

Pure Python + numpy — no bpy import, so unit-testable with plain dataclasses.

Blender local-coord convention (assumed by the fix formulas):
- Camera-local x = right, y = up, z = backwards from viewing direction.
- Positive Euler-Z-delta rotates the camera to look further LEFT
  (right-hand rule around camera's up-axis).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .report import CheckResult, SceneMutation

# ── Fix constants ──
GROUND_ENLARGE_FACTOR = 1.5  # ×1.5 per iteration until horizontal edge is gone
DOF_MIN_FSTOP = 4.0
EXPOSURE_STEP_STOPS = 1.0
COMPOSITION_YAW_DAMPING = 0.5  # take half the required yaw per iter to avoid overshoot


@dataclass(frozen=True)
class SceneState:
    """Snapshot of the tunable scene attributes at iteration start."""

    cam_fov_x_rad: float
    cam_to_car_distance_m: float
    image_width: int
    image_height: int
    ground_current_scale: tuple[float, float, float]
    view_exposure_current: float
    dof_focus_object_name: str | None
    dof_fstop_current: float


def compute_fix(check: CheckResult, state: SceneState) -> SceneMutation | None:
    """Return the SceneMutation for the given failing check, or None if the
    check is already passing (nothing to fix) or the fix isn't applicable.
    """
    if check.passed:
        return None
    dispatch = {
        "car_fully_in_frame": _fix_camera_shift,
        "composition_rule_of_thirds": _fix_camera_yaw,
        "ground_infinite": _fix_ground_scale,
        "sharpness_on_car_roi": _fix_dof_focus,
        "exposure_clipping": _fix_exposure_adjust,
    }
    handler = dispatch.get(check.name)
    if handler is None:
        return None
    return handler(check, state)


def _fix_camera_shift(check: CheckResult, state: SceneState) -> SceneMutation:
    """Shift camera along its local x/y so the car lands inside the margin.

    Meters = ndc_offset × frame_dim_at_car_distance.
    frame_width_at_distance = 2 × distance × tan(FOV/2).
    Sign convention: shifting camera right (+x) moves subject left in frame,
    so we shift TOWARD the cut-off edge to bring the car back into the frame.
    """
    off_x_right = check.details.get("off_x_right", 0.0)
    off_x_left = check.details.get("off_x_left", 0.0)
    off_y_top = check.details.get("off_y_top", 0.0)
    off_y_bot = check.details.get("off_y_bot", 0.0)

    frame_w = 2.0 * state.cam_to_car_distance_m * math.tan(state.cam_fov_x_rad / 2.0)
    frame_h = frame_w * state.image_height / state.image_width

    net_off_x = off_x_right - off_x_left  # >0 → right-cutoff → shift cam right
    net_off_y = off_y_top - off_y_bot  # >0 → top-cutoff → shift cam up
    dx = net_off_x * frame_w
    dy = net_off_y * frame_h

    return SceneMutation(
        fix_class="cam_lateral_shift",
        cam_delta_local=(dx, dy, 0.0),
        details={
            "net_off_x": net_off_x,
            "net_off_y": net_off_y,
            "frame_w_at_car": frame_w,
        },
    )


def _fix_camera_yaw(check: CheckResult, state: SceneState) -> SceneMutation:
    """Rotate camera around its local Z (yaw) so saliency lands closer to
    the nearest rule-of-thirds power-point.

    Formula: yaw_rad = (target_x - centroid_x) / image_width × FOV_X.
    Damping halves the correction to avoid overshoot on the next iter.
    """
    centroid_x = check.details.get("centroid_x", state.image_width / 2.0)
    target_x = check.details.get("target_x", state.image_width / 2.0)
    delta_px = target_x - centroid_x
    yaw_rad = (delta_px / state.image_width) * state.cam_fov_x_rad * COMPOSITION_YAW_DAMPING
    return SceneMutation(
        fix_class="cam_yaw_toward_thirds",
        cam_rotation_delta_z_rad=yaw_rad,
        details={
            "centroid_x": centroid_x,
            "target_x": target_x,
            "delta_px": delta_px,
            "yaw_rad": yaw_rad,
        },
    )


def _fix_ground_scale(check: CheckResult, state: SceneState) -> SceneMutation:
    """Multiply ground plane scale by GROUND_ENLARGE_FACTOR."""
    return SceneMutation(
        fix_class="ground_scale_up",
        ground_scale_factor=GROUND_ENLARGE_FACTOR,
        details={
            "current_scale_x": float(state.ground_current_scale[0]),
            "factor": GROUND_ENLARGE_FACTOR,
            "horizontal_lines_count": check.details.get("horizontal_lines_count", 0.0),
        },
    )


def _fix_dof_focus(check: CheckResult, state: SceneState) -> SceneMutation:
    """Set DoF focus to the car and clamp aperture to a wide DoF stop."""
    fstop_target = max(DOF_MIN_FSTOP, state.dof_fstop_current)
    return SceneMutation(
        fix_class="dof_focus_on_car",
        dof_focus_car=True,
        dof_min_fstop=fstop_target,
        details={
            "laplacian_variance": check.details.get("laplacian_variance", 0.0),
            "previous_fstop": state.dof_fstop_current,
            "new_min_fstop": fstop_target,
        },
    )


def _fix_exposure_adjust(check: CheckResult, state: SceneState) -> SceneMutation:
    """One stop up or down depending on which end is clipped."""
    clip_low = check.details.get("clip_low", 0.0)
    clip_high = check.details.get("clip_high", 0.0)
    step = -EXPOSURE_STEP_STOPS if clip_high > clip_low else EXPOSURE_STEP_STOPS
    return SceneMutation(
        fix_class="exposure_adjust",
        view_exposure_delta=step,
        details={
            "clip_low": clip_low,
            "clip_high": clip_high,
            "step_stops": step,
            "previous_exposure": state.view_exposure_current,
        },
    )
