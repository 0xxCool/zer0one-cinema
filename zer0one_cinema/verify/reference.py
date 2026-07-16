"""Golden-Frame regression gate (v0.2.2+).

Adds an SSIM + PSNR check between a "current" frame and a matching
"golden" frame in a reference directory. Used as the R_regression gate
in CGVF verify runs when the CLI is invoked with `--ref <path>`.

Gate semantics:

* PASS  — mean-pixel-delta (1 - SSIM) is ≤ `reference_delta_max`.
* WARN  — SSIM is above the threshold but PSNR is unusually low
          (typical encoder-drift signature): 20 dB ≤ PSNR < 30 dB.
* FAIL  — SSIM is below the threshold OR PSNR < 20 dB.
* SKIP  — no matching golden frame exists (filename-based lookup).

The reference set is matched by filename: `frames/frame_0042.png` is
compared to `<reference_dir>/frame_0042.png`. That keeps the API
independent of frame-indexing across renders — the caller is
responsible for producing matching filenames.

Both metrics come from scikit-image, which is already an install-time
dep via the `[preflight]` extra — no new package added by this module.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

from .gates import load_frame_rgb
from .report import GateResult, VerifyStatus
from .thresholds import THRESHOLDS as TH

# PSNR bands used to distinguish "encoder drift" from "regression".
# Values are dB — higher is better.
PSNR_WARN_MIN: float = 20.0
PSNR_WARN_MAX: float = 30.0


def _round(metrics: dict[str, float]) -> dict[str, float]:
    return {k: round(float(v), 4) for k, v in metrics.items()}


def compute_reference_delta(
    current_rgb: np.ndarray,
    reference_rgb: np.ndarray,
) -> tuple[float, float]:
    """Return `(mean_pixel_delta, psnr_db)` between two RGB frames.

    `mean_pixel_delta` = `1 - SSIM` (so 0 is identical, 1 is opposite).
    PSNR is in decibels, ≥ 60 dB is effectively lossless, < 20 dB is
    visually broken. Both are computed on `data_range=1.0` because the
    frames are already normalised to `[0, 1]` by `load_frame_rgb`.
    """
    if current_rgb.shape != reference_rgb.shape:
        raise ValueError(
            f"reference frame shape {reference_rgb.shape} does not match "
            f"current frame shape {current_rgb.shape}"
        )
    ssim = float(
        structural_similarity(
            reference_rgb,
            current_rgb,
            data_range=1.0,
            channel_axis=2,
        )
    )
    # PSNR of identical frames is +Infinity (log10 of 1/0). Silence the
    # runtime warning skimage would otherwise emit; the returned inf is
    # already meaningful and serialised as JSON-null by json.dumps.
    with np.errstate(divide="ignore"):
        psnr = float(
            peak_signal_noise_ratio(reference_rgb, current_rgb, data_range=1.0)
        )
    return 1.0 - ssim, psnr


def gate_reference(
    current_rgb: np.ndarray,
    reference_path: Path,
) -> GateResult:
    """Compare `current_rgb` to the frame stored at `reference_path`.

    Returns a `GateResult` with `name="R_regression"`. Missing reference
    files SKIP (they're expected in the "new frame introduced" case).
    """
    if not reference_path.exists():
        return GateResult(
            name="R_regression",
            status=VerifyStatus.SKIP,
            metrics={"note_reference_missing": 1.0},
        )

    reference_rgb = load_frame_rgb(reference_path)
    try:
        delta, psnr = compute_reference_delta(current_rgb, reference_rgb)
    except ValueError as exc:
        return GateResult(
            name="R_regression",
            status=VerifyStatus.FAIL,
            metrics={"note_shape_mismatch": 1.0},
        ) if False else GateResult(  # keeps type checker happy
            name="R_regression",
            status=VerifyStatus.FAIL,
            metrics={"error": 1.0, "note": float(hash(str(exc)) % 10)},
        )

    delta_max = float(TH.get("reference_delta_max", 0.25))

    if delta <= delta_max and psnr >= PSNR_WARN_MAX:
        status = VerifyStatus.PASS
    elif delta <= delta_max and PSNR_WARN_MIN <= psnr < PSNR_WARN_MAX:
        status = VerifyStatus.WARN
    else:
        status = VerifyStatus.FAIL

    return GateResult(
        name="R_regression",
        status=status,
        metrics=_round(
            {
                "delta_1_minus_ssim": delta,
                "psnr_db": psnr,
                "threshold_delta_max": delta_max,
            }
        ),
    )
