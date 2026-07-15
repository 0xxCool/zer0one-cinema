"""Unit tests for preflight/fix_rules.py — deterministic scene mutations."""
from __future__ import annotations

import math

import pytest

from zer0one_cinema.preflight.fix_rules import (
    COMPOSITION_YAW_DAMPING,
    DOF_MIN_FSTOP,
    EXPOSURE_STEP_STOPS,
    GROUND_ENLARGE_FACTOR,
    SceneState,
    compute_fix,
)
from zer0one_cinema.preflight.report import CheckResult, SceneMutation


def _state() -> SceneState:
    return SceneState(
        cam_fov_x_rad=math.radians(40.0),
        cam_to_car_distance_m=5.0,
        image_width=1920,
        image_height=1080,
        ground_current_scale=(10.0, 10.0, 1.0),
        view_exposure_current=0.0,
        dof_focus_object_name=None,
        dof_fstop_current=2.8,
    )


def _fail(name: str, details: dict[str, float], magnitude: float = 0.1) -> CheckResult:
    return CheckResult(name=name, passed=False, magnitude=magnitude, details=details)


# ── dispatch ──────────────────────────────────────────────────────────────


def test_compute_fix_returns_none_for_passing_check() -> None:
    r = CheckResult(name="car_fully_in_frame", passed=True, magnitude=0.0, details={})
    assert compute_fix(r, _state()) is None


def test_compute_fix_returns_none_for_unknown_check() -> None:
    r = _fail("mystery_check", {}, magnitude=0.5)
    assert compute_fix(r, _state()) is None


# ── camera shift fix ──────────────────────────────────────────────────────


def test_fix_camera_shift_right_cutoff_moves_cam_right() -> None:
    """Car right-cutoff (off_x_right = 0.1) → cam moves +x."""
    check = _fail(
        "car_fully_in_frame",
        {"off_x_right": 0.1, "off_x_left": 0.0, "off_y_top": 0.0, "off_y_bot": 0.0, "z_min": 1.0},
        magnitude=0.1,
    )
    m = compute_fix(check, _state())
    assert isinstance(m, SceneMutation)
    assert m.fix_class == "cam_lateral_shift"
    assert m.cam_delta_local is not None
    dx, dy, dz = m.cam_delta_local
    assert dx > 0
    assert dy == pytest.approx(0.0)
    assert dz == pytest.approx(0.0)


def test_fix_camera_shift_top_cutoff_moves_cam_up() -> None:
    check = _fail(
        "car_fully_in_frame",
        {"off_x_right": 0.0, "off_x_left": 0.0, "off_y_top": 0.05, "off_y_bot": 0.0, "z_min": 1.0},
    )
    m = compute_fix(check, _state())
    assert m is not None and m.cam_delta_local is not None
    _, dy, _ = m.cam_delta_local
    assert dy > 0


def test_fix_camera_shift_uses_fov_and_distance_formula() -> None:
    """dx = net_off_x × 2 × distance × tan(FOV/2)."""
    state = _state()
    off = 0.1
    check = _fail(
        "car_fully_in_frame",
        {"off_x_right": off, "off_x_left": 0.0, "off_y_top": 0.0, "off_y_bot": 0.0, "z_min": 1.0},
    )
    m = compute_fix(check, state)
    assert m is not None and m.cam_delta_local is not None
    dx, _, _ = m.cam_delta_local
    expected = off * 2 * state.cam_to_car_distance_m * math.tan(state.cam_fov_x_rad / 2)
    assert dx == pytest.approx(expected)


# ── camera yaw fix ────────────────────────────────────────────────────────


def test_fix_camera_yaw_zero_when_centroid_equals_target() -> None:
    """No delta → no yaw."""
    check = _fail(
        "composition_rule_of_thirds",
        {"centroid_x": 640.0, "target_x": 640.0, "target_y": 360.0, "distance_px": 0.0, "threshold_px": 100.0, "centroid_y": 360.0},
    )
    m = compute_fix(check, _state())
    assert m is not None
    assert m.cam_rotation_delta_z_rad == pytest.approx(0.0)


def test_fix_camera_yaw_positive_when_target_right_of_centroid() -> None:
    """Target x=1280, centroid x=640 → subject should move right → +yaw."""
    check = _fail(
        "composition_rule_of_thirds",
        {"centroid_x": 640.0, "target_x": 1280.0, "target_y": 360.0, "distance_px": 300.0, "threshold_px": 100.0, "centroid_y": 360.0},
    )
    state = _state()
    m = compute_fix(check, state)
    assert m is not None
    assert m.cam_rotation_delta_z_rad is not None
    expected = (1280.0 - 640.0) / state.image_width * state.cam_fov_x_rad * COMPOSITION_YAW_DAMPING
    assert m.cam_rotation_delta_z_rad == pytest.approx(expected)


def test_fix_camera_yaw_negative_when_target_left_of_centroid() -> None:
    check = _fail(
        "composition_rule_of_thirds",
        {"centroid_x": 1200.0, "target_x": 640.0, "target_y": 360.0, "distance_px": 400.0, "threshold_px": 100.0, "centroid_y": 360.0},
    )
    m = compute_fix(check, _state())
    assert m is not None
    assert m.cam_rotation_delta_z_rad is not None
    assert m.cam_rotation_delta_z_rad < 0


# ── ground scale fix ──────────────────────────────────────────────────────


def test_fix_ground_scale_returns_enlarge_factor() -> None:
    check = _fail("ground_infinite", {"horizontal_lines_count": 3.0})
    m = compute_fix(check, _state())
    assert m is not None
    assert m.fix_class == "ground_scale_up"
    assert m.ground_scale_factor == GROUND_ENLARGE_FACTOR


# ── DoF focus fix ─────────────────────────────────────────────────────────


def test_fix_dof_focus_sets_car_focus_and_widens_dof() -> None:
    check = _fail(
        "sharpness_on_car_roi",
        {"laplacian_variance": 40.0, "threshold": 120.0},
    )
    m = compute_fix(check, _state())
    assert m is not None
    assert m.fix_class == "dof_focus_on_car"
    assert m.dof_focus_car is True
    assert m.dof_min_fstop == DOF_MIN_FSTOP


def test_fix_dof_focus_preserves_current_fstop_when_already_high() -> None:
    """If cam already stopped down to f/8, don't loosen."""
    state = SceneState(
        cam_fov_x_rad=math.radians(40),
        cam_to_car_distance_m=5.0,
        image_width=1920,
        image_height=1080,
        ground_current_scale=(10.0, 10.0, 1.0),
        view_exposure_current=0.0,
        dof_focus_object_name=None,
        dof_fstop_current=8.0,
    )
    check = _fail("sharpness_on_car_roi", {"laplacian_variance": 40.0})
    m = compute_fix(check, state)
    assert m is not None
    assert m.dof_min_fstop == 8.0


# ── exposure fix ──────────────────────────────────────────────────────────


def test_fix_exposure_step_down_on_highlight_clip() -> None:
    check = _fail(
        "exposure_clipping",
        {"clip_low": 0.001, "clip_high": 0.05, "threshold": 0.02},
    )
    m = compute_fix(check, _state())
    assert m is not None
    assert m.fix_class == "exposure_adjust"
    assert m.view_exposure_delta == -EXPOSURE_STEP_STOPS


def test_fix_exposure_step_up_on_shadow_clip() -> None:
    check = _fail(
        "exposure_clipping",
        {"clip_low": 0.05, "clip_high": 0.001, "threshold": 0.02},
    )
    m = compute_fix(check, _state())
    assert m is not None
    assert m.view_exposure_delta == EXPOSURE_STEP_STOPS
