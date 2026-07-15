"""Origin-fix: move each wheel-group's object origin to its geometric center.

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design:

    Sketchfab/TurboSquid GLBs typically have their wheel-object origins at
    (0, 0, 0) or at the vehicle's overall centroid. Rotating a wheel around
    such an origin makes the wheel *fly off* the vehicle instead of spinning
    in place — the RS6-turntable-v2 bug.

    The fix is to move the origin of each wheel object to the geometric
    center of its bounding box (which for a well-modelled wheel coincides
    with the axle center). Blender API: `bpy.ops.object.origin_set(
    type='ORIGIN_CENTER_OF_VOLUME')` per selected wheel object, guarded so
    parent transforms are unaffected.

    Idempotent: if origin is already at bbox-center (within 1 mm), no-op.

Depends on `wheel_detect` having identified WheelGroup instances first.
"""

from __future__ import annotations

from collections.abc import Iterable

from .wheel_detect import WheelGroup


def set_wheel_origins_to_center(wheel_groups: Iterable[WheelGroup]) -> dict[str, int]:
    """Move each wheel-group's object origin to its geometric center.

    Args:
        wheel_groups: detected wheel groups from `detect_wheels()`.

    Returns:
        Report dict with 'origins_moved' (count) and 'skipped' (count of
        already-centered wheels).

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "origin_fix.set_wheel_origins_to_center: implementation pending "
        "(Sprint 19 Phase 2, task S19-P2-origin_fix)."
    )
