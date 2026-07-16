"""Multi-frame verify: motion coherence gate + top-level verify_frames().

Gate C (motion) uses OpenCV's Farneback optical-flow across consecutive
frames — the only verify module that hard-depends on cv2 (installed via
the `[preflight]` extra). It gracefully SKIPs if cv2 is missing.

`verify_frames()` is the top-level entry the CLI + Python callers use:
scan a folder, run selected gates, aggregate per-gate PASS-rate, and
return a VerifyReport.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np

from .. import __version__
from .gates import GATES, _luminance, load_frame_rgb
from .report import FrameReport, GateResult, VerifyReport, VerifyStatus
from .thresholds import THRESHOLDS as TH
from .thresholds import apply_profile

MOTION_MAG_PIXEL_MIN = 1.0  # ignore pixels with < 1 px displacement
MOTION_ANGLE_TOL_DEG = 15.0  # ± tolerance around median flow angle
MOTION_MIN_MOVING_FRACTION = 0.02  # ≥ 2% of pixels must be moving to score at all


def _try_import_cv2() -> object | None:
    """Deferred import — motion gate is optional."""
    try:
        import cv2

        return cv2
    except ImportError:
        return None


def gate_motion(prev_rgb: np.ndarray, curr_rgb: np.ndarray) -> GateResult:
    """Gate C — Motion Coherence between two consecutive frames.

    Consistency = fraction of moving pixels whose flow direction is within
    ±MOTION_ANGLE_TOL_DEG of the median flow direction. Real motion blur
    should be highly consistent (single dominant direction). Random noise
    or jittery motion produces low consistency.

    Returns SKIP when cv2 is not installed or when barely any pixels moved
    (nothing to score — e.g. two identical frames).
    """
    cv2 = _try_import_cv2()
    if cv2 is None:
        return GateResult(
            name="C_motion",
            status=VerifyStatus.SKIP,
            metrics={"note_cv2_missing": 1.0},
        )

    prev_gray = (_luminance(prev_rgb) * 255).astype("uint8")
    curr_gray = (_luminance(curr_rgb) * 255).astype("uint8")
    flow = cv2.calcOpticalFlowFarneback(  # type: ignore[attr-defined]
        prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
    )
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])  # type: ignore[attr-defined]

    moving = mag > MOTION_MAG_PIXEL_MIN
    moving_frac = float(moving.mean())
    if moving_frac < MOTION_MIN_MOVING_FRACTION:
        return GateResult(
            name="C_motion",
            status=VerifyStatus.SKIP,
            metrics={"moving_fraction": round(moving_frac, 4)},
        )

    median_ang = float(np.median(ang[moving]))
    diff = np.abs(ang[moving] - median_ang)
    diff = np.minimum(diff, 2 * np.pi - diff)
    consistency = float((diff < np.deg2rad(MOTION_ANGLE_TOL_DEG)).mean())

    min_ok = TH.get("motion_blur_direction_consistency_min", 0.85)
    status = VerifyStatus.PASS if consistency >= min_ok else VerifyStatus.FAIL
    return GateResult(
        name="C_motion",
        status=status,
        metrics={
            "direction_consistency": round(consistency, 4),
            "moving_fraction": round(moving_frac, 4),
        },
    )


def _discover_frames(frames_dir: Path) -> list[Path]:
    """Return sorted list of frame files in a folder (PNG + JPG)."""
    exts = (".png", ".jpg", ".jpeg")
    frames = sorted(p for p in frames_dir.iterdir() if p.suffix.lower() in exts)
    return frames


def _demote_warn_to_fail(gate: GateResult) -> GateResult:
    """--strict: treat WARN as FAIL (used for regression gating)."""
    if gate.status == VerifyStatus.WARN:
        return GateResult(name=gate.name, status=VerifyStatus.FAIL, metrics=gate.metrics)
    return gate


def _overall_status(reports: Iterable[FrameReport]) -> VerifyStatus:
    """Roll up per-frame status: worst wins (FAIL > WARN > PASS > SKIP)."""
    order = {
        VerifyStatus.FAIL: 3,
        VerifyStatus.WARN: 2,
        VerifyStatus.PASS: 1,
        VerifyStatus.SKIP: 0,
    }
    worst = VerifyStatus.PASS
    for fr in reports:
        for g in fr.gates:
            if order[g.status] > order[worst]:
                worst = g.status
    return worst


def _pass_rates(reports: list[FrameReport]) -> dict[str, float]:
    """Per-gate PASS fraction across all frames (SKIP excluded from denominator)."""
    per_gate: dict[str, tuple[int, int]] = {}  # name → (pass_count, considered_count)
    for fr in reports:
        for g in fr.gates:
            if g.status == VerifyStatus.SKIP:
                continue
            p, n = per_gate.get(g.name, (0, 0))
            per_gate[g.name] = (p + (1 if g.status == VerifyStatus.PASS else 0), n + 1)
    return {name: round(p / n, 4) if n else 0.0 for name, (p, n) in per_gate.items()}


def _resolve_gates(gates_requested: Iterable[str] | None) -> list[str]:
    """Turn a user-supplied gate list (or None) into a resolved order.

    None → all 5 single-frame gates + motion.
    """
    if gates_requested is None:
        return [*GATES.keys(), "motion"]
    return [g.strip() for g in gates_requested if g.strip()]


def verify_frames(
    frames_dir: str | Path,
    gates: Iterable[str] | None = None,
    reference_dir: str | Path | None = None,
    strict: bool = False,
    profile: str = "standard",
) -> VerifyReport:
    """Run selected CGVF gates on every frame in `frames_dir`.

    Args:
        frames_dir: folder containing PNG/JPG frames (sorted alphabetically).
        gates: subset of {lighting, material, motion, composition, atmosphere,
               grading} — None → all 6.
        reference_dir: currently unused (Golden-Frame regression is v0.3+).
        strict: if True, WARN status is demoted to FAIL in the roll-up.
        profile: named threshold set (e.g. "standard", "night_neon"). Applied
               globally for the duration of this call. Unknown names raise
               KeyError.

    Returns:
        VerifyReport with per-frame gate results + overall status + per-gate
        PASS-rate. Callers translate `.overall` into an exit code.
    """
    # Route thresholds through the profile before any gate runs. Gates read
    # `THRESHOLDS` at call-time, so this switch propagates to A/B/D/E/F and
    # the motion gate in one place.
    apply_profile(profile)

    frames_path = Path(frames_dir)
    frame_files = _discover_frames(frames_path)
    if not frame_files:
        return VerifyReport(
            version=__version__,
            frames=(),
            overall=VerifyStatus.SKIP,
            gate_pass_rate={},
            reference_dir=str(reference_dir) if reference_dir else None,
        )

    resolved = _resolve_gates(gates)
    run_motion = "motion" in resolved
    single_frame_gates = [g for g in resolved if g in GATES]

    # Cache loaded frames so motion gate can pair-index without re-loading
    loaded: dict[str, np.ndarray] = {}

    frame_reports: list[FrameReport] = []
    for i, fpath in enumerate(frame_files):
        rgb = loaded.get(str(fpath))
        if rgb is None:
            rgb = load_frame_rgb(fpath)
            loaded[str(fpath)] = rgb

        gate_results: list[GateResult] = [GATES[g](rgb) for g in single_frame_gates]

        if run_motion:
            if i == 0:
                # No previous frame available — motion gate skips for frame 0
                gate_results.append(
                    GateResult(
                        name="C_motion",
                        status=VerifyStatus.SKIP,
                        metrics={"note_first_frame": 1.0},
                    )
                )
            else:
                prev_path = frame_files[i - 1]
                prev_rgb = loaded.get(str(prev_path))
                if prev_rgb is None:
                    prev_rgb = load_frame_rgb(prev_path)
                    loaded[str(prev_path)] = prev_rgb
                gate_results.append(gate_motion(prev_rgb, rgb))

        if strict:
            gate_results = [_demote_warn_to_fail(g) for g in gate_results]

        frame_reports.append(
            FrameReport(frame_path=str(fpath), gates=tuple(gate_results))
        )

        # LRU-ish cache: keep only the last 2 frames in memory
        if i >= 2:
            loaded.pop(str(frame_files[i - 2]), None)

    return VerifyReport(
        version=__version__,
        frames=tuple(frame_reports),
        overall=_overall_status(frame_reports),
        gate_pass_rate=_pass_rates(frame_reports),
        reference_dir=str(reference_dir) if reference_dir else None,
    )
