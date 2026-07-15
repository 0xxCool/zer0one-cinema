"""Origin-fix: move each wheel-group's object origin to its geometric center.

Sketchfab/TurboSquid GLBs typically ship wheel objects with their origin at
(0, 0, 0) or at the vehicle's overall centroid. Rotating such an object
makes the wheel *fly off* the vehicle instead of spinning in place — that
was the RS6-turntable-v2 bug we solved by hand.

This module automates the fix by moving each wheel's object origin to the
detected wheel-center (from `wheel_detect.WheelGroup.center`). The
implementation is:

    1. Compute `delta = new_origin_world - obj.location` (the shift).
    2. Move all vertices of the mesh by `-delta` (in local coords) so the
       geometry stays in the same world position.
    3. Set `obj.location = new_origin_world`.

Idempotent: if the current origin is already within 1 mm of the target,
the operation is a no-op and no ChangeRecord is emitted.

Only rotating wheel-meshes (`wheel.meshes`) are re-origined. Static parts
(`wheel.static_meshes` — brake calipers, disc-brackets) keep their
original origins so they remain fixed to the chassis when the wheel spins.

Testable without bpy: `MutableObject` + `VertexList` are protocols; the
tests use dataclass mocks that satisfy them.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, MutableSequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .wheel_detect import WheelGroup

# ==========================================================================
# Protocols — testable without bpy
# ==========================================================================


class VertexLike(Protocol):
    """One vertex — its `co` (coordinate) is a mutable 3-vector."""

    co: MutableSequence[float]


class VertexData(Protocol):
    """Container for a mesh's vertex list."""

    vertices: Iterable[VertexLike]


class MutableObject(Protocol):
    """A Blender object with mutable `.location` and mutable `.data.vertices`."""

    name: str
    location: MutableSequence[float]
    data: VertexData


# ==========================================================================
# Data structures
# ==========================================================================


@dataclass(frozen=True)
class OriginChangeRecord:
    """Record of one object's origin move (for rollback)."""

    object_name: str
    old_location: tuple[float, float, float]
    new_location: tuple[float, float, float]
    delta_meters: float  # magnitude of the shift


@dataclass(frozen=True)
class OriginFixReport:
    """Aggregate report of one origin-fix operation."""

    origins_moved: int
    skipped_already_centered: int
    per_wheel: dict[str, tuple[OriginChangeRecord, ...]]


# ==========================================================================
# Constants
# ==========================================================================

# Objects whose origin is already within this distance of the target are
# left unchanged (idempotence guarantee).
_ORIGIN_MATCH_TOLERANCE_METERS = 1e-3


# ==========================================================================
# Core operation
# ==========================================================================


def _read_location(obj: MutableObject) -> np.ndarray:
    """Read obj.location as a (3,) float64 array."""
    loc = obj.location
    return np.array([float(loc[0]), float(loc[1]), float(loc[2])], dtype=np.float64)


def _write_location(obj: MutableObject, new_loc: np.ndarray) -> None:
    """Write obj.location. Assigns element-wise to preserve the underlying type."""
    obj.location[0] = float(new_loc[0])
    obj.location[1] = float(new_loc[1])
    obj.location[2] = float(new_loc[2])


def _shift_vertices(obj: MutableObject, delta_local: np.ndarray) -> None:
    """Shift every vertex of the mesh by `delta_local` (in local coords).

    Called with the negated origin-shift so the mesh stays put in world space
    while the origin moves.
    """
    dx, dy, dz = float(delta_local[0]), float(delta_local[1]), float(delta_local[2])
    for vert in obj.data.vertices:
        vert.co[0] += dx
        vert.co[1] += dy
        vert.co[2] += dz


def set_origin_to_center(
    obj: MutableObject,
    new_origin_world: tuple[float, float, float],
) -> OriginChangeRecord | None:
    """Move an object's origin to `new_origin_world` without displacing its geometry.

    Args:
        obj: any object satisfying MutableObject (e.g. bpy.types.Object).
        new_origin_world: target world-space origin (x, y, z).

    Returns:
        `OriginChangeRecord` describing the move, or `None` if the origin
        was already within 1 mm of the target (idempotent no-op).
    """
    target = np.array(new_origin_world, dtype=np.float64)
    current = _read_location(obj)
    delta = target - current
    delta_magnitude = float(np.linalg.norm(delta))

    if delta_magnitude < _ORIGIN_MATCH_TOLERANCE_METERS:
        return None

    # Shift vertices by -delta so world-space geometry stays fixed
    _shift_vertices(obj, -delta)
    old_loc = (float(current[0]), float(current[1]), float(current[2]))
    _write_location(obj, target)

    return OriginChangeRecord(
        object_name=obj.name,
        old_location=old_loc,
        new_location=(float(target[0]), float(target[1]), float(target[2])),
        delta_meters=delta_magnitude,
    )


# ==========================================================================
# Top-level entry
# ==========================================================================


def _iter_rotating_objects(wheel: WheelGroup) -> Iterator[MutableObject]:
    """Yield each rotating mesh in a wheel-group that also looks like a MutableObject.

    Some meshes (in tests, for instance) may not have `.data.vertices` — we
    silently skip those rather than crash. In production every `bpy.types.Object`
    of mesh type has them.
    """
    for mesh in wheel.meshes:
        if hasattr(mesh, "location") and hasattr(mesh, "data") and hasattr(mesh.data, "vertices"):
            yield mesh  # type: ignore[misc]


def set_wheel_origins_to_center(wheel_groups: Iterable[WheelGroup]) -> OriginFixReport:
    """Move every rotating wheel-mesh's origin to its wheel-group center.

    Static meshes (`wheel.static_meshes` — caliper, brake-disc bracket) are
    NOT re-origined; they stay attached to the chassis so they don't spin
    with the wheel.

    Args:
        wheel_groups: iterable of `WheelGroup` from `detect_wheels()`.

    Returns:
        `OriginFixReport` with counts + per-wheel change records.
    """
    per_wheel: dict[str, list[OriginChangeRecord]] = {}
    moved = 0
    skipped = 0

    for wheel in wheel_groups:
        records: list[OriginChangeRecord] = []
        for obj in _iter_rotating_objects(wheel):
            rec = set_origin_to_center(obj, wheel.center)
            if rec is None:
                skipped += 1
            else:
                records.append(rec)
                moved += 1
        per_wheel[wheel.label] = records

    return OriginFixReport(
        origins_moved=moved,
        skipped_already_centered=skipped,
        per_wheel={label: tuple(recs) for label, recs in per_wheel.items()},
    )
