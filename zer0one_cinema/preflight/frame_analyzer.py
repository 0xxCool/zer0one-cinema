"""Pure-Python analyzer for one EEVEE preview frame.

Input: numpy.ndarray (H, W, 3) uint8 BGR (OpenCV convention) + PreflightContext
Output: list[CheckResult]

No bpy import; no filesystem I/O. Callable from unit tests with synthetic
numpy arrays. See docs/research/preflight-frame-qa.md §2 for check
semantics and threshold rationale.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .report import CheckResult


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

    Filled in during Phase P4.
    """
    raise NotImplementedError("phase P4")
