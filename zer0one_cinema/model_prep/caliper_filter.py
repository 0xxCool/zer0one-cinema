"""Caliper filter: convenience API for accessing wheel's static (non-rotating) meshes.

The actual caliper-vs-rim separation happens inside
`wheel_detect.aggregate_wheel_meshes()` — every `WheelGroup` returned by
`detect_wheels()` already has `.static_meshes` populated with brake calipers
and disc brackets that must NOT rotate with the wheel.

This module exists as a thin wrapper for API discoverability — users who
grep for "caliper" find this file rather than needing to know that the
logic lives inside the wheel-detection pipeline.
"""

from __future__ import annotations

from collections.abc import Sequence

from .bbox_utils import MeshLike
from .wheel_detect import WheelGroup


def filter_static_from_wheel(wheel: WheelGroup) -> Sequence[MeshLike]:
    """Return the static (non-rotating) meshes of a wheel-group.

    These are typically brake calipers and disc-brackets — geometry that is
    close to the wheel but attached to the chassis, so it must stay still
    when the wheel spins.

    Args:
        wheel: a WheelGroup from `detect_wheels()` (already-populated).

    Returns:
        Tuple of MeshLike objects. Empty if `wheel.static_meshes` is empty.
    """
    return wheel.static_meshes


def filter_all_static(wheels: Sequence[WheelGroup]) -> list[MeshLike]:
    """Return the flattened list of static meshes from all wheels."""
    result: list[MeshLike] = []
    for w in wheels:
        result.extend(w.static_meshes)
    return result
