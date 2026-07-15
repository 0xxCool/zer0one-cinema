"""Pure-Python analyzer for one EEVEE preview frame.

Input: numpy.ndarray (H, W, 3) uint8 BGR (OpenCV convention) + PreflightContext.
Output: list[CheckResult].

No bpy import; no filesystem I/O. Callable from unit tests with synthetic
numpy arrays. See docs/research/preflight-frame-qa.md §2 for check
semantics and threshold rationale.

cv2 is imported lazily inside individual check functions so the module
loads without opencv installed — checks that hit cv2 will raise a clear
ImportError only when invoked.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .report import CheckResult

# Composition: max distance from a rule-of-thirds power-point (fraction of min-dim)
COMPOSITION_MAX_DIST_FRAC = 0.15
# Sharpness: Laplacian-variance threshold; calibrated for 1080p Cycles renders
SHARPNESS_LAPLACIAN_MIN = 120.0
# Exposure: max fraction of clipped pixels per end
EXPOSURE_CLIP_MAX = 0.02
# Ground-edge Hough: horizontal-line angle tolerance and minimum length fraction
GROUND_HORIZONTAL_ANGLE_DEG = 5.0
GROUND_MIN_LINE_LENGTH_FRAC = 0.4


@dataclass(frozen=True)
class BBoxNDC:
    """Car bounding-box in Blender's normalized-device coords.

    Convention: (0,0)=bottom-left, (1,1)=top-right, z>0 means in-front-of-camera.
    Values outside [0,1] are allowed and encode "outside the frame".
    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float  # min over all 8 bbox corners
    z_max: float


@dataclass(frozen=True)
class PreflightContext:
    """All the non-image inputs the analyzer needs."""

    bbox_ndc: BBoxNDC
    image_width: int
    image_height: int
    ndc_margin: float = 0.04  # 4% safety margin per side


def analyze_frame(frame_bgr: np.ndarray, ctx: PreflightContext) -> list[CheckResult]:
    """Run all 5 preflight checks on a single BGR preview frame.

    Order matches the fix priority in the loop (car-in-frame first — no
    point analyzing composition of an off-screen car). Any check that
    cannot run (e.g. cv2 missing) surfaces its ImportError so the loop
    can decide whether to skip or abort.
    """
    return [
        _check_car_fully_in_frame(ctx),
        _check_ground_infinite(frame_bgr, ctx),
        _check_composition_rule_of_thirds(frame_bgr, ctx),
        _check_sharpness_on_car_roi(frame_bgr, ctx),
        _check_exposure_clipping(frame_bgr),
    ]


def _check_car_fully_in_frame(ctx: PreflightContext) -> CheckResult:
    """Verifies all 8 bbox corners are in front of camera AND within margin.

    Pure geometry — no image data needed.
    """
    b = ctx.bbox_ndc
    m = ctx.ndc_margin
    z_ok = b.z_min > 0
    x_ok = b.x_min > m and b.x_max < 1 - m
    y_ok = b.y_min > m and b.y_max < 1 - m
    passed = z_ok and x_ok and y_ok

    off_x_left = max(0.0, m - b.x_min)
    off_x_right = max(0.0, b.x_max - (1 - m))
    off_y_bot = max(0.0, m - b.y_min)
    off_y_top = max(0.0, b.y_max - (1 - m))
    z_penalty = max(0.0, -b.z_min) * 10.0  # heavy: behind camera is unrecoverable

    magnitude = max(off_x_left, off_x_right, off_y_bot, off_y_top, z_penalty)
    return CheckResult(
        name="car_fully_in_frame",
        passed=passed,
        magnitude=float(magnitude),
        details={
            "off_x_left": float(off_x_left),
            "off_x_right": float(off_x_right),
            "off_y_bot": float(off_y_bot),
            "off_y_top": float(off_y_top),
            "z_min": float(b.z_min),
        },
    )


def _check_composition_rule_of_thirds(
    frame_bgr: np.ndarray, ctx: PreflightContext
) -> CheckResult:
    """Saliency centroid must be near one of the 4 rule-of-thirds power-points.

    Uses OpenCV's StaticSaliencyFineGrained — requires opencv-contrib-python.
    """
    import cv2

    sal = cv2.saliency.StaticSaliencyFineGrained_create()  # type: ignore[attr-defined]
    ok, sal_map = sal.computeSaliency(frame_bgr)
    if not ok or sal_map is None:
        return CheckResult(
            name="composition_rule_of_thirds",
            passed=True,
            magnitude=0.0,
            details={"note_saliency_failed": 1.0},
        )
    sal_uint8 = (sal_map * 255).astype("uint8")
    m = cv2.moments(sal_uint8)
    if m["m00"] < 1e-6:
        return CheckResult(
            name="composition_rule_of_thirds",
            passed=True,
            magnitude=0.0,
            details={"note_empty_saliency": 1.0},
        )
    cx = float(m["m10"] / m["m00"])
    cy = float(m["m01"] / m["m00"])
    w, h = ctx.image_width, ctx.image_height
    thirds = [
        (w / 3.0, h / 3.0),
        (2.0 * w / 3.0, h / 3.0),
        (w / 3.0, 2.0 * h / 3.0),
        (2.0 * w / 3.0, 2.0 * h / 3.0),
    ]
    distances = [((cx - tx) ** 2 + (cy - ty) ** 2) ** 0.5 for tx, ty in thirds]
    nearest_idx = int(np.argmin(distances))
    nearest_target = thirds[nearest_idx]
    d = float(distances[nearest_idx])
    threshold_px = COMPOSITION_MAX_DIST_FRAC * min(w, h)
    passed = d < threshold_px
    magnitude = max(0.0, d - threshold_px) / max(w, h)
    return CheckResult(
        name="composition_rule_of_thirds",
        passed=passed,
        magnitude=float(magnitude),
        details={
            "centroid_x": cx,
            "centroid_y": cy,
            "target_x": float(nearest_target[0]),
            "target_y": float(nearest_target[1]),
            "distance_px": d,
            "threshold_px": float(threshold_px),
        },
    )


def _check_ground_infinite(
    frame_bgr: np.ndarray, ctx: PreflightContext
) -> CheckResult:
    """No visible horizontal Hough-line in the strip below the car bbox.

    A visible horizontal edge below the car means the ground plane is too
    small and its far edge is in-frame.
    """
    import cv2

    h_img = ctx.image_height
    w_img = ctx.image_width
    # NDC y=0 is bottom-of-image; pixel y=0 is top-of-image. Convert car
    # bottom-in-frame to pixel-y: bbox.y_min (lower ndc) → higher pixel-y.
    bbox_bottom_pixel_y = int(np.clip((1.0 - ctx.bbox_ndc.y_min) * h_img, 0, h_img))
    below = frame_bgr[bbox_bottom_pixel_y:, :]
    if below.size == 0 or below.shape[0] < 20:
        return CheckResult(
            name="ground_infinite",
            passed=True,
            magnitude=0.0,
            details={"note_below_strip_empty": 1.0},
        )
    gray = cv2.cvtColor(below, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 180)
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=80,
        minLineLength=int(w_img * GROUND_MIN_LINE_LENGTH_FRAC),
        maxLineGap=20,
    )
    horizontal_count = 0
    if lines is not None:
        # cv2 versions return either shape (N, 1, 4) or (N, 4) — flatten defensively
        for line in lines:
            x1, y1, x2, y2 = np.asarray(line).ravel().tolist()
            angle_deg = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if abs(angle_deg) < GROUND_HORIZONTAL_ANGLE_DEG:
                horizontal_count += 1
    passed = horizontal_count == 0
    magnitude = min(1.0, horizontal_count / 5.0)
    return CheckResult(
        name="ground_infinite",
        passed=passed,
        magnitude=float(magnitude),
        details={"horizontal_lines_count": float(horizontal_count)},
    )


def _check_sharpness_on_car_roi(
    frame_bgr: np.ndarray, ctx: PreflightContext
) -> CheckResult:
    """Laplacian-variance on the car bbox ROI must exceed SHARPNESS_LAPLACIAN_MIN.

    Uses cv2.Laplacian on the region-of-interest containing the car; low
    variance signals blur / out-of-focus.
    """
    import cv2

    w_img, h_img = ctx.image_width, ctx.image_height
    b = ctx.bbox_ndc
    x_min_px = int(np.clip(b.x_min * w_img, 0, w_img - 1))
    x_max_px = int(np.clip(b.x_max * w_img, 1, w_img))
    # NDC y flipped when converting to pixel space
    y_min_px = int(np.clip((1.0 - b.y_max) * h_img, 0, h_img - 1))
    y_max_px = int(np.clip((1.0 - b.y_min) * h_img, 1, h_img))
    if x_max_px - x_min_px < 10 or y_max_px - y_min_px < 10:
        return CheckResult(
            name="sharpness_on_car_roi",
            passed=True,
            magnitude=0.0,
            details={"note_roi_too_small": 1.0},
        )
    roi = frame_bgr[y_min_px:y_max_px, x_min_px:x_max_px]
    lap = cv2.Laplacian(roi, cv2.CV_64F)
    variance = float(lap.var())
    passed = variance > SHARPNESS_LAPLACIAN_MIN
    magnitude = max(0.0, SHARPNESS_LAPLACIAN_MIN - variance) / SHARPNESS_LAPLACIAN_MIN
    return CheckResult(
        name="sharpness_on_car_roi",
        passed=passed,
        magnitude=float(magnitude),
        details={
            "laplacian_variance": variance,
            "threshold": SHARPNESS_LAPLACIAN_MIN,
        },
    )


def _check_exposure_clipping(frame_bgr: np.ndarray) -> CheckResult:
    """Fraction of Y-channel pixels at 0 or 255 must stay below EXPOSURE_CLIP_MAX."""
    import cv2

    y_chan = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)[..., 0]
    clip_low = float((y_chan == 0).mean())
    clip_high = float((y_chan == 255).mean())
    passed = clip_low < EXPOSURE_CLIP_MAX and clip_high < EXPOSURE_CLIP_MAX
    magnitude = max(0.0, max(clip_low, clip_high) - EXPOSURE_CLIP_MAX)
    return CheckResult(
        name="exposure_clipping",
        passed=passed,
        magnitude=float(magnitude),
        details={
            "clip_low": clip_low,
            "clip_high": clip_high,
            "threshold": EXPOSURE_CLIP_MAX,
        },
    )
