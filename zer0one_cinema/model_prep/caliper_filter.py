"""Caliper filter: separate rotating (rim + tire) from static (caliper + brake-disc).

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design (from `docs/research/wheel-detection-methods.md` §6):

    Once `wheel_detect` has identified a wheel-group, some sub-meshes within
    that group must NOT rotate with the wheel — brake calipers and brake
    discs are chassis-mounted and stay static while the wheel spins around
    them. Rotating them causes the visual bug we saw in RS6-turntable-v2
    where the caliper flew around the wheel.

    Geometric test: for each sub-mesh in a wheel-group, compute the radial
    distance from the sub-mesh's bbox center to the wheel's rolling-axis.
    If that distance is > 20% of the wheel radius, the sub-mesh is likely
    a caliper (extends outward from the hub) — mark it as static.

    Whitelist-based: if the geometric test is ambiguous (distance ∈ [15%,
    25%] of radius), fall back to name-heuristic ("caliper", "brake",
    "disc" → static). If both are ambiguous, default to rotating (fail-safe
    — a stationary rim is uglier than a spinning caliper).

    Returns an updated `WheelGroup` with `static_meshes` populated.
"""

from __future__ import annotations

from .wheel_detect import WheelGroup


def filter_static_from_wheel(wheel: WheelGroup) -> WheelGroup:
    """Return a new WheelGroup with static (non-rotating) meshes separated.

    The input WheelGroup has `meshes` = all sub-meshes; the output has
    `meshes` = only rotating parts (rim + tire) and `static_meshes` =
    calipers + brake discs.

    Args:
        wheel: a WheelGroup from `detect_wheels()`, may have static parts
            still mixed into `meshes`.

    Returns:
        New WheelGroup with clean separation.

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "caliper_filter.filter_static_from_wheel: implementation pending "
        "(Sprint 19 Phase 2, task S19-P2-caliper_filter)."
    )
