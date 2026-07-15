"""All CGVF gate thresholds in one place — the calibration surface.

Sourced from ~/zer0one-web/.claude/skills/cinema-grade-verification/
references/gate-thresholds.md. Tune here, not inside gate functions.

Grouping mirrors the CGVF-Framework: A_lighting / B_material / D_composition /
E_atmosphere / F_grading + reference-comparison. Motion (Gate C) lives in
sequence.py because its thresholds relate to a different data-shape
(2 frames vs. 1).
"""
from __future__ import annotations

from typing import Final

# All values are floats; JSON-serialisable, monkey-patchable in tests.
THRESHOLDS: Final[dict[str, float]] = {
    # ── Gate A: Lighting Signature ──
    "key_fill_ratio_min": 3.0,        # Bright-half / dark-half mean
    "key_fill_ratio_max": 6.0,
    "shadow_density_min": 0.15,       # fraction of pixels < 0.05 luminance
    "highlight_clip_max": 0.001,      # fraction of pixels ≥ 0.995
    "rim_edge_ratio_min": 1.5,        # Body-edge luminance / body-inner
    # ── Gate B: Material Response ──
    "body_bright_pixel_frac_min": 0.08,   # frac of body-pixels with luminance > 0.7
    "wet_asphalt_peak_count_min": 5,      # bright pixels below vehicle
    # ── Gate D: Composition ──
    "auto_center_offset_min": 0.15,   # Auto-Center ≥ 15% off frame-center
    "negative_space_min": 0.20,       # ≥ 20% frame free of subject silhouette
    "auto_fill_max": 0.60,            # Auto fills ≤ 60% of frame
    # ── Gate E: Atmosphere & Depth ──
    "bg_detail_min": 0.40,            # Bg-Non-Black-Pixel-fraction
    "volumetric_shafts_min": 2,       # Nacht-only (nicht in v0.2)
    # ── Gate F: Color Grading ──
    "corner_center_ratio_max": 0.75,  # Vignette floor
    "aspect_ratio_target": 2.39,
    "aspect_ratio_tolerance": 0.05,
    "shadow_hue_min_deg": 160.0,      # teal
    "shadow_hue_max_deg": 220.0,
    "highlight_hue_min_deg": 20.0,    # orange
    "highlight_hue_max_deg": 60.0,
    "noise_std_min": 4.0,
    "noise_std_max": 12.0,
    # ── Reference-Comparison (used by cli/verify.py --ref) ──
    "reference_delta_max": 0.25,      # 25% mean-pixel-delta
}
