"""Rolling-axis convenience API for accessing a wheel's rotation axis.

The actual rolling-axis determination happens inside `wheel_detect` — for a
detected car, every wheel's rolling axis is the vehicle's PCA right-axis
(wheels roll around it). It's stored in `WheelGroup.rolling_axis_vector`.

This module exists as a thin wrapper for API discoverability — users who
grep for "rolling_axis" find this file rather than needing to know the
axis lives inside the wheel-group dataclass.
"""

from __future__ import annotations

from .wheel_detect import WheelGroup


def infer_rolling_axis(wheel: WheelGroup) -> tuple[float, float, float]:
    """Return the wheel's rolling-axis vector (world coords, unit).

    Args:
        wheel: a WheelGroup from `detect_wheels()`.

    Returns:
        (x, y, z) unit vector; the axis around which the wheel rotates.
    """
    return wheel.rolling_axis_vector
