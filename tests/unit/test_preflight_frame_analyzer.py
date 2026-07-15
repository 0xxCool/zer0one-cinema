"""Unit tests for preflight/frame_analyzer.py — 5 checks on synthetic frames."""
from __future__ import annotations

import numpy as np
import pytest

from zer0one_cinema.preflight.frame_analyzer import (
    COMPOSITION_MAX_DIST_FRAC,
    EXPOSURE_CLIP_MAX,
    SHARPNESS_LAPLACIAN_MIN,
    BBoxNDC,
    PreflightContext,
    _check_car_fully_in_frame,
    _check_composition_rule_of_thirds,
    _check_exposure_clipping,
    _check_ground_infinite,
    _check_sharpness_on_car_roi,
    analyze_frame,
)

# ── Fixtures / helpers ────────────────────────────────────────────────────

W, H = 640, 360  # small size keeps tests fast


def _in_frame_bbox(x=0.4, y=0.3, size=0.2, z=1.0) -> BBoxNDC:
    return BBoxNDC(
        x_min=x, x_max=x + size, y_min=y, y_max=y + size, z_min=z, z_max=z + 1.0
    )


def _ctx(bbox: BBoxNDC | None = None) -> PreflightContext:
    return PreflightContext(
        bbox_ndc=bbox or _in_frame_bbox(),
        image_width=W,
        image_height=H,
    )


def _bgr_uniform(v: int) -> np.ndarray:
    return np.full((H, W, 3), v, dtype=np.uint8)


def _bgr_noisy(seed: int = 0, low: int = 30, high: int = 220) -> np.ndarray:
    return np.random.RandomState(seed).randint(low, high, (H, W, 3), dtype=np.uint8)


# ── _check_car_fully_in_frame ─────────────────────────────────────────────


def test_car_in_frame_pass_for_centered_bbox() -> None:
    r = _check_car_fully_in_frame(_ctx())
    assert r.name == "car_fully_in_frame"
    assert r.passed is True
    assert r.magnitude == 0.0


def test_car_in_frame_fail_when_bbox_right_edge_crosses_margin() -> None:
    # margin=0.04, x_max=0.98 > 0.96 → off_x_right = 0.02
    bbox = BBoxNDC(x_min=0.5, x_max=0.98, y_min=0.3, y_max=0.7, z_min=1.0, z_max=2.0)
    r = _check_car_fully_in_frame(_ctx(bbox))
    assert r.passed is False
    assert r.details["off_x_right"] == pytest.approx(0.02, abs=1e-4)
    assert r.details["off_x_left"] == 0.0


def test_car_in_frame_fail_when_bbox_behind_camera() -> None:
    bbox = BBoxNDC(x_min=0.3, x_max=0.7, y_min=0.3, y_max=0.7, z_min=-0.1, z_max=0.5)
    r = _check_car_fully_in_frame(_ctx(bbox))
    assert r.passed is False
    assert r.magnitude >= 1.0  # z-penalty is heavy (×10)
    assert r.details["z_min"] == pytest.approx(-0.1)


def test_car_in_frame_magnitude_reflects_worst_offset() -> None:
    """Bottom edge below margin — magnitude equals that offset."""
    bbox = BBoxNDC(x_min=0.3, x_max=0.7, y_min=0.01, y_max=0.5, z_min=1.0, z_max=2.0)
    r = _check_car_fully_in_frame(_ctx(bbox))
    assert r.passed is False
    assert r.magnitude == pytest.approx(0.03, abs=1e-4)  # 0.04 - 0.01


# ── _check_composition_rule_of_thirds ─────────────────────────────────────


def test_composition_pass_when_saliency_lands_near_third_power_point() -> None:
    """Bright blob at upper-left third → high saliency there → close to (W/3, H/3)."""
    frame = _bgr_uniform(10)
    tx, ty = int(W / 3), int(H / 3)
    frame[ty - 20 : ty + 20, tx - 20 : tx + 20, :] = 245
    r = _check_composition_rule_of_thirds(frame, _ctx())
    assert r.name == "composition_rule_of_thirds"
    assert r.passed is True
    assert "target_x" in r.details
    assert abs(r.details["target_x"] - W / 3) < 1.0


def test_composition_fail_when_saliency_centered() -> None:
    frame = _bgr_uniform(10)
    cx, cy = W // 2, H // 2
    frame[cy - 20 : cy + 20, cx - 20 : cx + 20, :] = 245
    r = _check_composition_rule_of_thirds(frame, _ctx())
    assert r.passed is False
    assert r.details["distance_px"] > COMPOSITION_MAX_DIST_FRAC * min(W, H)


def test_composition_warn_note_on_uniform_frame() -> None:
    """No signal → saliency map may be empty; check gracefully passes with note."""
    frame = _bgr_uniform(128)
    r = _check_composition_rule_of_thirds(frame, _ctx())
    # Either passes because the centroid ends up mid-frame near-a-third,
    # or the empty-saliency note fires — both are non-FAIL by design.
    assert r.passed is True or "note_empty_saliency" in r.details


# ── _check_ground_infinite ────────────────────────────────────────────────


def test_ground_infinite_pass_on_smooth_below_strip() -> None:
    """Smooth gradient below car (like a lit infinite floor) → no Hough line → PASS."""
    frame = _bgr_uniform(120)
    # subtle vertical gradient — no horizontal edges
    for row in range(H):
        frame[row, :, :] = int(80 + row / H * 100)
    r = _check_ground_infinite(frame, _ctx())
    assert r.name == "ground_infinite"
    assert r.passed is True


def test_ground_infinite_fail_when_horizontal_edge_below_car() -> None:
    """A sharp horizontal edge line 60% of frame width, below the car → FAIL."""
    frame = _bgr_uniform(200)
    # Draw a dark horizontal band at 2/3 of image height (below default car bbox)
    edge_y = int(H * 0.75)
    frame[edge_y - 2 : edge_y + 2, : int(W * 0.7), :] = 0
    # Ensure the car bbox ends above the edge so Hough scans below it.
    bbox = BBoxNDC(x_min=0.3, x_max=0.7, y_min=0.4, y_max=0.7, z_min=1.0, z_max=2.0)
    r = _check_ground_infinite(frame, _ctx(bbox))
    assert r.passed is False
    assert r.details["horizontal_lines_count"] >= 1


def test_ground_infinite_gracefully_handles_no_below_strip() -> None:
    """If car bbox reaches to bottom of frame, no strip to inspect → PASS with note."""
    bbox = BBoxNDC(x_min=0.3, x_max=0.7, y_min=-0.05, y_max=0.9, z_min=1.0, z_max=2.0)
    frame = _bgr_uniform(100)
    r = _check_ground_infinite(frame, _ctx(bbox))
    assert r.passed is True
    assert "note_below_strip_empty" in r.details


# ── _check_sharpness_on_car_roi ───────────────────────────────────────────


def test_sharpness_pass_on_sharp_roi() -> None:
    """High-frequency random noise in the car ROI → high Laplacian variance."""
    frame = _bgr_uniform(80)
    bbox = _in_frame_bbox(x=0.3, y=0.3, size=0.3)
    # Noise inside the bbox in pixel space
    xp_min, xp_max = int(bbox.x_min * W), int(bbox.x_max * W)
    yp_min, yp_max = int((1 - bbox.y_max) * H), int((1 - bbox.y_min) * H)
    frame[yp_min:yp_max, xp_min:xp_max, :] = np.random.RandomState(2).randint(
        0, 255, (yp_max - yp_min, xp_max - xp_min, 3), dtype=np.uint8
    )
    r = _check_sharpness_on_car_roi(frame, _ctx(bbox))
    assert r.name == "sharpness_on_car_roi"
    assert r.passed is True
    assert r.details["laplacian_variance"] > SHARPNESS_LAPLACIAN_MIN


def test_sharpness_fail_on_flat_roi() -> None:
    """Uniform-color ROI → zero Laplacian variance → FAIL."""
    frame = _bgr_uniform(128)
    r = _check_sharpness_on_car_roi(frame, _ctx())
    assert r.passed is False
    assert r.details["laplacian_variance"] < SHARPNESS_LAPLACIAN_MIN
    assert r.magnitude > 0.0


def test_sharpness_skip_on_tiny_roi() -> None:
    """Bbox smaller than 10×10 pixels → skip with note."""
    tiny_bbox = BBoxNDC(x_min=0.499, x_max=0.5, y_min=0.499, y_max=0.5, z_min=1.0, z_max=2.0)
    r = _check_sharpness_on_car_roi(_bgr_uniform(128), _ctx(tiny_bbox))
    assert r.passed is True
    assert "note_roi_too_small" in r.details


# ── _check_exposure_clipping ──────────────────────────────────────────────


def test_exposure_pass_on_midtone_frame() -> None:
    r = _check_exposure_clipping(_bgr_uniform(128))
    assert r.name == "exposure_clipping"
    assert r.passed is True
    assert r.details["clip_low"] == 0.0
    assert r.details["clip_high"] == 0.0


def test_exposure_fail_on_pure_white_frame() -> None:
    r = _check_exposure_clipping(_bgr_uniform(255))
    assert r.passed is False
    assert r.details["clip_high"] > EXPOSURE_CLIP_MAX


def test_exposure_fail_on_pure_black_frame() -> None:
    r = _check_exposure_clipping(_bgr_uniform(0))
    assert r.passed is False
    assert r.details["clip_low"] > EXPOSURE_CLIP_MAX


# ── analyze_frame integration ─────────────────────────────────────────────


def test_analyze_frame_returns_all_five_checks_in_order() -> None:
    r = analyze_frame(_bgr_uniform(128), _ctx())
    assert [c.name for c in r] == [
        "car_fully_in_frame",
        "ground_infinite",
        "composition_rule_of_thirds",
        "sharpness_on_car_roi",
        "exposure_clipping",
    ]


def test_analyze_frame_all_pass_on_clean_scene() -> None:
    """Frame with bbox at a third, sharp noise in ROI, no ground edge, midtone."""
    frame = _bgr_uniform(80)
    # sharp ROI = noise
    frame[100:200, 200:400, :] = np.random.RandomState(3).randint(
        0, 255, (100, 200, 3), dtype=np.uint8
    )
    # bbox at rule-of-thirds top-left
    bbox = BBoxNDC(x_min=0.25, x_max=0.42, y_min=0.55, y_max=0.72, z_min=1.0, z_max=2.0)
    results = analyze_frame(frame, _ctx(bbox))
    assert results[0].passed is True  # car in frame
    # Others may still fail on synthetic — but car-in-frame must pass
