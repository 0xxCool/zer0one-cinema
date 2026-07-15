"""Unit tests for zer0one_cinema.verify.gates — 5 single-frame CGVF gates."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from zer0one_cinema.verify.gates import (
    GATES,
    _car_mask_heuristic,
    _luminance,
    _rgb_to_hue_deg,
    gate_atmosphere,
    gate_composition,
    gate_grading,
    gate_lighting,
    gate_material,
    load_frame_rgb,
)
from zer0one_cinema.verify.report import GateResult, VerifyStatus


def _cinemascope(h: int = 300, w: int = 717) -> tuple[int, int]:
    """Return dims for exact 2.39 aspect (717/300 = 2.39)."""
    return h, w


# ── helpers ───────────────────────────────────────────────────────────────


def test_luminance_black_returns_zero() -> None:
    rgb = np.zeros((5, 5, 3), dtype=np.float32)
    assert np.allclose(_luminance(rgb), 0.0)


def test_luminance_white_returns_one() -> None:
    rgb = np.ones((5, 5, 3), dtype=np.float32)
    assert np.allclose(_luminance(rgb), 1.0)


def test_luminance_pure_green_uses_bt709_weight() -> None:
    rgb = np.zeros((1, 1, 3), dtype=np.float32)
    rgb[0, 0, 1] = 1.0
    assert _luminance(rgb)[0, 0] == pytest.approx(0.7152, abs=1e-4)


def test_rgb_to_hue_red_is_zero_deg() -> None:
    rgb = np.zeros((1, 1, 3), dtype=np.float32)
    rgb[0, 0, 0] = 1.0
    assert _rgb_to_hue_deg(rgb)[0, 0] == pytest.approx(0.0, abs=1e-4)


def test_rgb_to_hue_green_is_120_deg() -> None:
    rgb = np.zeros((1, 1, 3), dtype=np.float32)
    rgb[0, 0, 1] = 1.0
    assert _rgb_to_hue_deg(rgb)[0, 0] == pytest.approx(120.0, abs=1e-3)


def test_rgb_to_hue_blue_is_240_deg() -> None:
    rgb = np.zeros((1, 1, 3), dtype=np.float32)
    rgb[0, 0, 2] = 1.0
    assert _rgb_to_hue_deg(rgb)[0, 0] == pytest.approx(240.0, abs=1e-3)


# ── load_frame_rgb ────────────────────────────────────────────────────────


def test_load_frame_rgb_shape_and_range(tmp_path: Path) -> None:
    p = tmp_path / "frame.png"
    Image.new("RGB", (128, 64), color=(200, 100, 50)).save(p)
    rgb = load_frame_rgb(p)
    assert rgb.shape == (64, 128, 3)
    assert rgb.dtype == np.float32
    assert rgb.min() >= 0.0 and rgb.max() <= 1.0
    assert rgb[0, 0, 0] == pytest.approx(200 / 255.0, abs=1e-4)


def test_load_frame_rgb_accepts_str_path(tmp_path: Path) -> None:
    p = tmp_path / "frame.png"
    Image.new("RGB", (4, 4)).save(p)
    rgb = load_frame_rgb(str(p))
    assert rgb.shape == (4, 4, 3)


# ── car_mask_heuristic ────────────────────────────────────────────────────


def test_car_mask_heuristic_covers_dark_center_pixels() -> None:
    rgb = np.full((100, 100, 3), 0.8, dtype=np.float32)
    rgb[35:65, 35:65, :] = 0.1
    mask = _car_mask_heuristic(rgb)
    center_frac = mask[35:65, 35:65].mean()
    assert center_frac > 0.9


def test_car_mask_heuristic_empty_when_uniform_bright() -> None:
    rgb = np.full((100, 100, 3), 0.9, dtype=np.float32)
    mask = _car_mask_heuristic(rgb)
    assert mask.sum() == 0


# ── gate_lighting ─────────────────────────────────────────────────────────


def test_gate_lighting_pass_on_balanced_dark_bright_frame() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.35, dtype=np.float32)
    rgb[: h // 4, :, :] = 0.02  # dense shadows (17% of frame)
    rgb[h // 2 :, :, :] = 0.85  # bright half — bright-mean drives KFR
    result = gate_lighting(rgb)
    assert result.name == "A_lighting"
    assert result.status == VerifyStatus.PASS
    assert "key_fill_ratio" in result.metrics
    assert 3.0 <= result.metrics["key_fill_ratio"] <= 6.0


def test_gate_lighting_fail_when_no_shadows() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.5, dtype=np.float32)
    result = gate_lighting(rgb)
    assert result.status == VerifyStatus.FAIL
    assert result.metrics["shadow_density"] < 0.15


def test_gate_lighting_fail_on_highlight_clip() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.5, dtype=np.float32)
    rgb[:50, :, :] = 0.001  # some shadow
    rgb[h - 50 :, :, :] = 1.0  # heavy clipping
    result = gate_lighting(rgb)
    assert result.status == VerifyStatus.FAIL
    assert result.metrics["highlight_clip"] > 0.01


# ── gate_material ─────────────────────────────────────────────────────────


def test_gate_material_pass_with_bright_body_and_ground_peaks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Injects a proper subject mask so we can test the bright-body metric directly.

    The dark-cluster heuristic in `_car_mask_heuristic` structurally cannot
    detect pixels > 0.7 luminance (it filters them out). Real usage would
    plug in a semantic-segmentation mask. Monkey-patch simulates that.
    """
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.3, dtype=np.float32)
    body_y = slice(int(h * 0.3), int(h * 0.6))
    body_x = slice(int(w * 0.3), int(w * 0.6))
    rgb[body_y, body_x, :] = 0.85  # bright car body
    rgb[int(h * 0.8) :, :, :] = 0.6  # bright ground

    # Provide the body-region mask directly, bypassing the dark-cluster fallback.
    body_mask = np.zeros((h, w), dtype=bool)
    body_mask[body_y, body_x] = True
    monkeypatch.setattr(
        "zer0one_cinema.verify.gates._car_mask_heuristic",
        lambda _rgb: body_mask,
    )

    result = gate_material(rgb)
    assert result.name == "B_material"
    assert result.status == VerifyStatus.PASS
    assert result.metrics["body_bright_frac"] >= 0.08


def test_gate_material_fail_with_all_dark_frame() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.05, dtype=np.float32)
    result = gate_material(rgb)
    assert result.status == VerifyStatus.FAIL


# ── gate_composition ──────────────────────────────────────────────────────


def test_gate_composition_warn_when_mask_empty() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.9, dtype=np.float32)
    result = gate_composition(rgb)
    assert result.name == "D_composition"
    assert result.status == VerifyStatus.WARN
    assert result.metrics["heuristic_mask_empty"] == 1.0


def test_gate_composition_pass_when_off_center_moderate_fill() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.9, dtype=np.float32)
    # Small subject in upper-left third — offset from center
    rgb[int(h * 0.25) : int(h * 0.45), int(w * 0.25) : int(w * 0.4), :] = 0.1
    result = gate_composition(rgb)
    assert result.status == VerifyStatus.PASS
    assert result.metrics["auto_center_offset"] >= 0.15


def test_gate_composition_fail_when_dead_centered() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.9, dtype=np.float32)
    # Subject symmetrically around frame center
    rgb[int(h * 0.4) : int(h * 0.6), int(w * 0.45) : int(w * 0.55), :] = 0.1
    result = gate_composition(rgb)
    assert result.status == VerifyStatus.FAIL
    assert result.metrics["auto_center_offset"] < 0.15


# ── gate_atmosphere ───────────────────────────────────────────────────────


def test_gate_atmosphere_pass_with_bright_bg() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.6, dtype=np.float32)
    # Dark central subject → bg fraction is bright
    rgb[int(h * 0.3) : int(h * 0.7), int(w * 0.3) : int(w * 0.7), :] = 0.1
    result = gate_atmosphere(rgb)
    assert result.name == "E_atmosphere"
    assert result.status == VerifyStatus.PASS


def test_gate_atmosphere_fail_with_black_bg() -> None:
    h, w = _cinemascope()
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[int(h * 0.3) : int(h * 0.7), int(w * 0.3) : int(w * 0.7), :] = 0.5
    result = gate_atmosphere(rgb)
    assert result.status == VerifyStatus.FAIL
    assert result.metrics["bg_detail"] < 0.4


# ── gate_grading ──────────────────────────────────────────────────────────


def _make_graded_frame(h: int, w: int) -> np.ndarray:
    """A frame passing vignette + aspect + teal-shadows + orange-highlights.

    Colors chosen so post-recolor luminance still lands in the shadow (<0.3)
    resp. highlight (>0.7) buckets, so `gate_grading`'s own re-derivation
    picks them up.
    """
    rgb = np.full((h, w, 3), 0.4, dtype=np.float32)  # neutral base

    # Corners: paint teal (0.0, 0.3, 0.5) → luminance = 0.25 → shadow bucket
    csize = min(h, w) // 8
    teal = np.array([0.0, 0.3, 0.5], dtype=np.float32)  # hue ≈ 216° ✓
    rgb[:csize, :csize, :] = teal
    rgb[:csize, -csize:, :] = teal
    rgb[-csize:, :csize, :] = teal
    rgb[-csize:, -csize:, :] = teal

    # Center: paint bright orange (1.0, 0.7, 0.2) → luminance ≈ 0.73 → highlight bucket
    center_size = min(h, w) // 4
    cy, cx = h // 2, w // 2
    orange = np.array([1.0, 0.7, 0.2], dtype=np.float32)  # hue ≈ 36° ✓
    rgb[cy - center_size : cy + center_size, cx - center_size : cx + center_size, :] = orange
    return rgb


def test_gate_grading_pass_on_teal_orange_2_39_with_vignette() -> None:
    rgb = _make_graded_frame(300, 717)  # 2.39 aspect
    result = gate_grading(rgb)
    assert result.name == "F_grading"
    assert result.status == VerifyStatus.PASS
    assert abs(result.metrics["aspect_ratio"] - 2.39) <= 0.01


def test_gate_grading_fail_on_wrong_aspect() -> None:
    rgb = _make_graded_frame(300, 400)  # 1.33 aspect — wrong
    result = gate_grading(rgb)
    assert result.status == VerifyStatus.FAIL


def test_gate_grading_fail_on_flat_no_vignette() -> None:
    h, w = 300, 717
    rgb = np.full((h, w, 3), 0.5, dtype=np.float32)
    result = gate_grading(rgb)
    assert result.status == VerifyStatus.FAIL
    assert result.metrics["vignette_corner_center"] >= 0.75


def test_gate_grading_warn_when_no_teal_orange_but_aspect_and_vignette_ok() -> None:
    h, w = 300, 717
    rgb = np.full((h, w, 3), 0.4, dtype=np.float32)
    # Vignette: bright center
    csize = min(h, w) // 4
    cy, cx = h // 2, w // 2
    rgb[cy - csize : cy + csize, cx - csize : cx + csize, :] = 0.9
    # No teal/orange, just neutral tones → WARN
    result = gate_grading(rgb)
    assert result.status == VerifyStatus.WARN


# ── GATES registry ────────────────────────────────────────────────────────


def test_gates_registry_has_five_single_frame_gates() -> None:
    assert set(GATES.keys()) == {
        "lighting",
        "material",
        "composition",
        "atmosphere",
        "grading",
    }


def test_gates_registry_all_callables_returning_gateresult() -> None:
    h, w = _cinemascope()
    rgb = np.full((h, w, 3), 0.5, dtype=np.float32)
    for name, fn in GATES.items():
        r = fn(rgb)
        assert isinstance(r, GateResult), f"{name} returned {type(r)}"
        assert isinstance(r.metrics, dict) and r.metrics, f"{name} metrics empty"
