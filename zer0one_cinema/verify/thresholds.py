"""All CGVF gate thresholds in one place — the calibration surface.

Two-layer design (v0.2.1+):

1. `BASE_THRESHOLDS` — the daylight-studio defaults (identical to v0.2.0
   for backward compatibility). Sourced from ~/zer0one-web/.claude/skills/
   cinema-grade-verification/references/gate-thresholds.md.

2. `PROFILE_OVERRIDES` — named threshold-deltas for looks that would
   otherwise produce false-positive FAILs. Selected via `--profile <name>`
   on the CLI or `profile=` on `verify_frames()`.

Currently shipped profiles:

* `standard` — daylight studio (default; identical to v0.2.0 behaviour)
* `night_neon` — NfS-style night hero-reveal (cyan/magenta neon rims,
  metallic dark body, orbit-camera). Widens A_lighting, B_material,
  C_motion, F_grading thresholds where the look legitimately falls
  outside daylight-studio expectations.

Motion (Gate C) lives in sequence.py because its thresholds relate to a
different data-shape (2 frames vs. 1), but its `motion_blur_direction_
consistency_min` key still routes through the profile system.
"""
from __future__ import annotations

from typing import Final

BASE_THRESHOLDS: Final[dict[str, float]] = {
    # ── Gate A: Lighting Signature ──
    "key_fill_ratio_min": 3.0,        # Bright-half / dark-half mean
    "key_fill_ratio_max": 6.0,
    "shadow_density_min": 0.15,       # fraction of pixels < 0.05 luminance
    "highlight_clip_max": 0.001,      # fraction of pixels ≥ 0.995
    "rim_edge_ratio_min": 1.5,        # Body-edge luminance / body-inner
    # ── Gate B: Material Response ──
    "body_bright_pixel_frac_min": 0.08,   # frac of body-pixels with luminance > 0.7
    "wet_asphalt_peak_count_min": 5,      # bright pixels below vehicle
    # ── Gate C: Motion Coherence (used by sequence.gate_motion) ──
    "motion_blur_direction_consistency_min": 0.85,
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


PROFILE_OVERRIDES: Final[dict[str, dict[str, float]]] = {
    # Daylight studio — the v0.2.0 defaults. Explicitly empty override dict
    # so `--profile standard` is a no-op instead of a KeyError.
    "standard": {},

    # NfS-style night hero-reveal (see /cinema landing case-study):
    #  * cyan+magenta neon rim reflections → shadow/highlight hues live
    #    in 190-290° (cyan-blue-magenta) not 20-60° (orange).
    #  * dark metallic body → 0% "bright body pixel" fraction is normal.
    #  * high-contrast night lighting → key/fill ratio 10-25 not 3-6.
    #  * neon panel outside frame center → vignette-corner-center can
    #    exceed 1.0 (corners brighter than center) — fine per design.
    #  * orbit camera → optical-flow directions on car+ground diverge,
    #    consistency drops to 0.05-0.30. That is the look, not a bug.
    "night_neon": {
        "key_fill_ratio_max": 25.0,
        "body_bright_pixel_frac_min": 0.0,
        "corner_center_ratio_max": 5.0,
        "shadow_hue_min_deg": 190.0,
        "shadow_hue_max_deg": 290.0,
        "highlight_hue_min_deg": 180.0,
        "highlight_hue_max_deg": 330.0,
        "motion_blur_direction_consistency_min": 0.05,
        # Web-video delivery (16:9), not theatrical cinemascope (2.39). The
        # /cinema case-study ships as 1920×1080 mp4/webm — matching that.
        "aspect_ratio_target": 1.7778,
        "aspect_ratio_tolerance": 0.02,
        # Hero-reveal orbits center the subject BY DESIGN (rule-of-thirds
        # doesn't apply). Also the subject occupies less of the frame than
        # a poster shot — allow the tighter negative-space budget.
        "auto_center_offset_min": 0.0,
        "negative_space_min": 0.60,
    },
}


def available_profiles() -> tuple[str, ...]:
    """Public helper — CLI uses this to build `--profile` choices."""
    return tuple(PROFILE_OVERRIDES.keys())


def resolve_thresholds(profile: str = "standard") -> dict[str, float]:
    """Return the effective threshold dict for `profile`.

    `standard` returns a copy of BASE_THRESHOLDS; other profiles return
    BASE with their overrides merged on top. Unknown profile names raise
    a KeyError with the available names in the message, so callers get
    a clear error rather than a silent standard-fallback.
    """
    if profile not in PROFILE_OVERRIDES:
        available = ", ".join(available_profiles())
        raise KeyError(
            f"unknown verify profile {profile!r} — available: {available}"
        )
    merged = dict(BASE_THRESHOLDS)
    merged.update(PROFILE_OVERRIDES[profile])
    return merged


# ────────────────────────────────────────────────────────────────
# Backwards-compatibility surface:
#
# v0.2.0 exposed a module-level `THRESHOLDS` dict that gates + tests
# imported directly. To preserve that API we keep the name pointing at
# a mutable dict that always mirrors the active profile. Profile-aware
# callers should prefer `resolve_thresholds()`; legacy imports keep
# working because `apply_profile()` mutates this same dict in place.
# ────────────────────────────────────────────────────────────────
THRESHOLDS: dict[str, float] = dict(BASE_THRESHOLDS)


def apply_profile(profile: str = "standard") -> dict[str, float]:
    """Rewrite the module-level `THRESHOLDS` dict to reflect `profile`.

    Returns the (same) dict so callers can chain the call. This is the
    entry point the CLI and `verify_frames()` use — every gate function
    reads its cutoffs from `THRESHOLDS` at call time, so a single call
    at the top of a verify run switches every gate in one place.
    """
    effective = resolve_thresholds(profile)
    THRESHOLDS.clear()
    THRESHOLDS.update(effective)
    return THRESHOLDS
