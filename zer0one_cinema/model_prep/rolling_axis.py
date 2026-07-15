"""Rolling-axis detection: determine which local axis a wheel rolls around.

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design (from `docs/research/wheel-detection-methods.md`):

    A well-modelled wheel is a squashed cylinder — its local bounding box
    has three dimensions where one is noticeably shorter than the other two
    (the tire's width). That shortest axis is the rolling axis.

    Ratios to test (post ground_anchor, in world coords):
        sizes = sorted(bbox.size)  # short, mid, long
        aspect_short_mid = sizes[0] / sizes[1]  # should be ≤ 0.6 for a wheel
        aspect_mid_long  = sizes[1] / sizes[2]  # should be ≥ 0.85 (rim ≈ tire)

    Rolling axis = the local axis parallel to the shortest bbox dimension.

    Edge cases:
    - Racing wheels are flatter (aspect_short_mid ~ 0.3); still works.
    - Off-road tires can approach 0.6; threshold should be permissive.
    - If ratios don't match (aspect_short_mid > 0.6 AND aspect_mid_long < 0.85),
      it's probably NOT a wheel — return None so caller can fall back.
"""

from __future__ import annotations

from typing import Literal

from .wheel_detect import WheelGroup

RollingAxisLiteral = Literal["x", "y", "z"]


def infer_rolling_axis(wheel: WheelGroup) -> RollingAxisLiteral | None:
    """Determine which axis (x/y/z in world space) a wheel rolls around.

    Args:
        wheel: a detected wheel group.

    Returns:
        'x', 'y', or 'z' if a clear rolling axis is found; None if the
        input geometry doesn't look like a wheel (aspect ratios don't fit).

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "rolling_axis.infer_rolling_axis: implementation pending "
        "(Sprint 19 Phase 2, task S19-P2-rolling_axis)."
    )
