"""Ground-anchor: translate a vehicle scene so its lowest point sits on world z=0.

Uses `scene_world_aabb` from `bbox_utils` to find the *true* minimum z across
**all** meshes and **all** 8 bbox corners per mesh (not a sampled subset —
that was the RS6-v3 bug where wheels sank into the floor because only the
first few vertices of the first few meshes were sampled).

The scene is shifted by `-min_z` on the z-axis, applied to top-level objects
(their children move automatically via parent transform).

Idempotent: running twice = running once (within a 1e-6 float tolerance).
Deterministic: same input → identical output.

The heavy lifting is Blender-agnostic; `bpy` types satisfy the same protocol
used in unit tests, so we test with `numpy`-only mocks.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, TypedDict

from .bbox_utils import AABB, MeshLike, scene_world_aabb

_EPSILON_METRES = 1e-6


class TopLevelObject(Protocol):
    """Any object whose location is a mutable (x, y, z) sequence."""

    location: Sequence[float]


class GroundAnchorReport(TypedDict):
    """Result of a ground-anchor operation, for logging and rollback."""

    z_shift: float
    objects_moved: int
    idempotent: bool
    scene_aabb_before: tuple[float, float, float, float, float, float]  # min_x..max_z


def compute_z_shift(meshes: Iterable[MeshLike]) -> float:
    """Return the delta-z needed to place the scene's lowest point at z=0.

    Returns 0.0 (no-op) if min_z is already within 1e-6 metres of zero
    — that guarantees idempotence.
    """
    aabb: AABB = scene_world_aabb(meshes)
    if abs(aabb.min_z) < _EPSILON_METRES:
        return 0.0
    return -aabb.min_z


def apply_z_shift(top_level_objects: Iterable[TopLevelObject], dz: float) -> int:
    """Shift each top-level object's `location.z` by `dz`.

    Only top-level (root) objects need to be shifted; children move
    automatically via their parent's transform. A no-op if `dz == 0.0`.

    Returns:
        Number of objects whose location was updated.
    """
    if dz == 0.0:
        return 0
    count = 0
    for obj in top_level_objects:
        # Convert to list so we can mutate index 2 regardless of underlying type
        # (bpy uses a Vector; a plain list works for both Blender and tests)
        loc = list(obj.location)
        loc[2] = loc[2] + dz
        obj.location = loc
        count += 1
    return count


def ground_anchor(
    meshes: Iterable[MeshLike],
    top_level_objects: Iterable[TopLevelObject],
) -> GroundAnchorReport:
    """Anchor a vehicle scene so its lowest point sits on world z=0.

    Args:
        meshes: all mesh-like objects in the vehicle (used to compute the
            true scene min_z from bbox corners).
        top_level_objects: root-level objects whose `.location.z` will be
            shifted by `-min_z`. Children move automatically.

    Returns:
        A report dict with `z_shift`, `objects_moved`, `idempotent`,
        and the scene AABB before shifting (for provenance).
    """
    # Materialize meshes so we can compute both aabb and (implicitly) reuse them
    materialized = list(meshes)
    aabb = scene_world_aabb(materialized)
    dz = 0.0 if abs(aabb.min_z) < _EPSILON_METRES else -aabb.min_z
    idempotent = dz == 0.0
    moved = apply_z_shift(top_level_objects, dz)
    return GroundAnchorReport(
        z_shift=dz,
        objects_moved=moved,
        idempotent=idempotent,
        scene_aabb_before=(
            aabb.min_x,
            aabb.min_y,
            aabb.min_z,
            aabb.max_x,
            aabb.max_y,
            aabb.max_z,
        ),
    )
