"""The 5 single-frame CGVF gates: A_lighting, B_material, D_composition,
E_atmosphere, F_grading.

Migrated + refactored from ~/zer0one-web/.claude/skills/cinema-grade-
verification/scripts/verify_frame.py. numpy + Pillow only — the OpenCV-
specific motion gate (C) lives in sequence.py.

All gates return `GateResult`; input is `np.ndarray` shape (H, W, 3), float
in [0, 1], RGB channel order.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from .report import GateResult, VerifyStatus
from .thresholds import THRESHOLDS as TH


def load_frame_rgb(path: str | Path) -> np.ndarray:
    """Load PNG/JPG as float32 RGB in [0, 1], shape (H, W, 3)."""
    img = Image.open(str(path)).convert("RGB")
    return np.asarray(img, dtype=np.float32) / 255.0


def _luminance(rgb: np.ndarray) -> np.ndarray:
    """ITU-R BT.709 luminance from RGB in [0, 1]."""
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]


def _rgb_to_hue_deg(rgb: np.ndarray) -> np.ndarray:
    """HSV hue in degrees [0, 360). rgb is (H, W, 3), values in [0, 1]."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cmax = np.max(rgb, axis=-1)
    cmin = np.min(rgb, axis=-1)
    delta = cmax - cmin
    hue = np.zeros_like(cmax)
    mask = delta > 1e-6
    idx_r = mask & (cmax == r)
    idx_g = mask & (cmax == g)
    idx_b = mask & (cmax == b)
    hue[idx_r] = ((g[idx_r] - b[idx_r]) / delta[idx_r]) % 6
    hue[idx_g] = ((b[idx_g] - r[idx_g]) / delta[idx_g]) + 2
    hue[idx_b] = ((r[idx_b] - g[idx_b]) / delta[idx_b]) + 4
    return hue * 60.0  # type: ignore[no-any-return]


def _car_mask_heuristic(rgb: np.ndarray) -> np.ndarray:
    """Heuristic subject mask: darker-than-median pixels in the central 60% band.

    Fallback when no proper segmentation is available. Documented as heuristic
    in gate-thresholds.md — Gate D emits WARN (not FAIL) if the mask is empty.
    """
    lum = _luminance(rgb)
    h, w = lum.shape
    median = float(np.median(lum))
    mask = lum < median * 0.9  # darker than typical bg
    center = np.zeros_like(mask)
    center[int(h * 0.20) : int(h * 0.85), int(w * 0.20) : int(w * 0.80)] = True
    return mask & center


def _round_metrics(metrics: dict[str, float]) -> dict[str, float]:
    """Round to 4 decimal places for stable JSON snapshots."""
    return {k: round(float(v), 4) for k, v in metrics.items()}


def _worst_status(checks: dict[str, bool]) -> VerifyStatus:
    return VerifyStatus.FAIL if not all(checks.values()) else VerifyStatus.PASS


def gate_lighting(rgb: np.ndarray) -> GateResult:
    """Gate A — Lighting Signature: key/fill contrast, shadow density, highlight clip."""
    lum = _luminance(rgb)
    bright = lum[lum > np.median(lum)]
    dark = lum[lum < np.median(lum)]
    bright_mean = float(bright.mean()) if bright.size else 0.0
    dark_mean = float(dark.mean()) if dark.size else 1e-6
    kfr = bright_mean / max(dark_mean, 1e-6)
    shadow_density = float((lum < 0.05).mean())
    hi_clip = float((lum >= 0.995).mean())
    checks = {
        "key_fill_ratio": TH["key_fill_ratio_min"] <= kfr <= TH["key_fill_ratio_max"],
        "shadow_density": shadow_density >= TH["shadow_density_min"],
        "highlight_no_clip": hi_clip <= TH["highlight_clip_max"],
    }
    return GateResult(
        name="A_lighting",
        status=_worst_status(checks),
        metrics=_round_metrics({
            "key_fill_ratio": kfr,
            "shadow_density": shadow_density,
            "highlight_clip": hi_clip,
        }),
    )


def gate_material(rgb: np.ndarray) -> GateResult:
    """Gate B — Material Response: bright body pixels + wet-asphalt hints."""
    lum = _luminance(rgb)
    mask = _car_mask_heuristic(rgb)
    body_bright_frac = float((lum[mask] > 0.7).mean()) if mask.any() else 0.0
    h, _ = lum.shape
    below_y = int(h * 0.7)
    ground_lum = lum[below_y:, :]
    peaks = int((ground_lum > 0.5).sum())
    checks = {
        "body_bright_frac": body_bright_frac >= TH["body_bright_pixel_frac_min"],
        "wet_asphalt_peaks": peaks >= TH["wet_asphalt_peak_count_min"],
    }
    return GateResult(
        name="B_material",
        status=_worst_status(checks),
        metrics=_round_metrics({
            "body_bright_frac": body_bright_frac,
            "wet_asphalt_peaks": float(peaks),
        }),
    )


def gate_composition(rgb: np.ndarray) -> GateResult:
    """Gate D — Composition: subject offset, negative space, auto fill fraction.

    Emits WARN (not FAIL) when the heuristic car-mask is empty — verify runs
    on unknown-content frames so a missing subject shouldn't hard-fail.
    """
    mask = _car_mask_heuristic(rgb)
    h, w = mask.shape
    if not mask.any():
        return GateResult(
            name="D_composition",
            status=VerifyStatus.WARN,
            metrics={"heuristic_mask_empty": 1.0},
        )
    ys, xs = np.where(mask)
    cy = ys.mean() / h
    cx = xs.mean() / w
    offset = float(((cy - 0.5) ** 2 + (cx - 0.5) ** 2) ** 0.5)
    auto_fill = float(mask.mean())
    negative_space = 1.0 - auto_fill
    checks = {
        "auto_center_offset": offset >= TH["auto_center_offset_min"],
        "auto_fill": auto_fill <= TH["auto_fill_max"],
        "negative_space": negative_space >= TH["negative_space_min"],
    }
    return GateResult(
        name="D_composition",
        status=_worst_status(checks),
        metrics=_round_metrics({
            "auto_center_offset": offset,
            "auto_fill": auto_fill,
            "negative_space": negative_space,
        }),
    )


def gate_atmosphere(rgb: np.ndarray) -> GateResult:
    """Gate E — Atmosphere & Depth: background detail (non-black pixel fraction)."""
    lum = _luminance(rgb)
    mask = _car_mask_heuristic(rgb)
    bg = ~mask
    bg_detail = float((lum[bg] > 0.05).mean()) if bg.any() else 0.0
    checks = {"bg_detail": bg_detail >= TH["bg_detail_min"]}
    return GateResult(
        name="E_atmosphere",
        status=_worst_status(checks),
        metrics=_round_metrics({"bg_detail": bg_detail}),
    )


def gate_grading(rgb: np.ndarray) -> GateResult:
    """Gate F — Color Grading: aspect, vignette, teal-orange split-tone.

    Hard-fail on aspect + vignette (framing/grade fundamentals). Teal-orange
    hue targets are style choices → WARN if outside, PASS if inside, FAIL
    only when the hard checks also fail.
    """
    h, w = rgb.shape[:2]
    aspect = w / h
    lum = _luminance(rgb)
    csize = min(h, w) // 8
    corner = np.concatenate([
        lum[:csize, :csize].ravel(),
        lum[:csize, -csize:].ravel(),
        lum[-csize:, :csize].ravel(),
        lum[-csize:, -csize:].ravel(),
    ]).mean()
    center = lum[h // 2 - csize : h // 2 + csize, w // 2 - csize : w // 2 + csize].mean()
    corner_center = float(corner / max(center, 1e-6))
    hue = _rgb_to_hue_deg(rgb)
    shadow_mask = lum < 0.3
    highlight_mask = lum > 0.7
    shadow_hue_mean = float(hue[shadow_mask].mean()) if shadow_mask.any() else 0.0
    highlight_hue_mean = float(hue[highlight_mask].mean()) if highlight_mask.any() else 0.0

    aspect_ok = abs(aspect - TH["aspect_ratio_target"]) <= TH["aspect_ratio_tolerance"]
    vignette_ok = corner_center <= TH["corner_center_ratio_max"]
    shadow_teal_ok = TH["shadow_hue_min_deg"] <= shadow_hue_mean <= TH["shadow_hue_max_deg"]
    highlight_orange_ok = (
        TH["highlight_hue_min_deg"] <= highlight_hue_mean <= TH["highlight_hue_max_deg"]
    )

    if not (aspect_ok and vignette_ok):
        status = VerifyStatus.FAIL
    elif not (shadow_teal_ok and highlight_orange_ok):
        status = VerifyStatus.WARN
    else:
        status = VerifyStatus.PASS

    return GateResult(
        name="F_grading",
        status=status,
        metrics=_round_metrics({
            "aspect_ratio": aspect,
            "vignette_corner_center": corner_center,
            "shadow_hue_deg": shadow_hue_mean,
            "highlight_hue_deg": highlight_hue_mean,
        }),
    )


# Public registry — CLI + sequence.verify_frames() look up gates by name.
# Motion gate is registered in sequence.py to avoid a hard cv2 dependency here.
GATES = {
    "lighting": gate_lighting,
    "material": gate_material,
    "composition": gate_composition,
    "atmosphere": gate_atmosphere,
    "grading": gate_grading,
}
