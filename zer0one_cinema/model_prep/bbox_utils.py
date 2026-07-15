"""Bounding-box utilities for 3D meshes.

Core utility used by ground_anchor, wheel_detect, body_group, and other
model-prep modules. All functions accept iterables of `MeshLike` objects
and work with numpy arrays under the hood. **Blender-agnostic:** the
`MeshLike` protocol lets us unit-test without importing `bpy`.

The AABB (axis-aligned bounding box) values are computed by transforming
each mesh's 8 local bbox corners with its `matrix_world` and taking the
min/max across all corners. This is the correct way to compute a scene
AABB — the RS6-v3 bug was sampling only a few vertices of the first few
meshes, which missed the true min_z and made wheels sink into the floor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np


class MeshLike(Protocol):
    """Minimal interface satisfied by `bpy.types.Object` (mesh) and test mocks."""

    @property
    def matrix_world(self) -> Sequence[Sequence[float]]:
        """4x4 world transform as a row-major nested sequence."""
        ...

    @property
    def bound_box(self) -> Sequence[Sequence[float]]:
        """The 8 local-space corners of the mesh's bounding box, each (x, y, z)."""
        ...


@dataclass(frozen=True)
class AABB:
    """Axis-aligned bounding box in world space."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def size(self) -> tuple[float, float, float]:
        return (
            self.max_x - self.min_x,
            self.max_y - self.min_y,
            self.max_z - self.min_z,
        )

    @property
    def center(self) -> tuple[float, float, float]:
        return (
            (self.min_x + self.max_x) / 2.0,
            (self.min_y + self.max_y) / 2.0,
            (self.min_z + self.max_z) / 2.0,
        )


def world_bbox_corners(mesh: MeshLike) -> np.ndarray:
    """Return the 8 world-space corners of a mesh's local bounding box.

    Uses `matrix_world @ local_corner` for each of the 8 corners.
    Fully reproducible: identical inputs produce identical outputs.

    Returns:
        Array of shape (8, 3), dtype float64.

    Raises:
        ValueError: if matrix or bbox has the wrong shape.
    """
    matrix = np.asarray(mesh.matrix_world, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"matrix_world must be 4x4, got shape {matrix.shape}")

    local_corners = np.asarray(mesh.bound_box, dtype=np.float64)
    if local_corners.shape != (8, 3):
        raise ValueError(f"bound_box must be (8, 3), got shape {local_corners.shape}")

    # Convert (8, 3) -> homogeneous (8, 4) with w=1
    homogeneous = np.hstack([local_corners, np.ones((8, 1), dtype=np.float64)])
    # matrix @ homogeneous.T => (4, 8), transpose back to (8, 4), drop w-column
    transformed = (matrix @ homogeneous.T).T
    return transformed[:, :3]


def scene_world_aabb(meshes: Iterable[MeshLike]) -> AABB:
    """Compute the tight axis-aligned bounding box of a scene in world space.

    Iterates all meshes, transforms each mesh's 8 local corners to world
    space, and returns the AABB enclosing all corners. Deterministic.

    Args:
        meshes: iterable of mesh-like objects (any object exposing
            `matrix_world` and `bound_box`).

    Returns:
        The tight world-space AABB enclosing all input meshes.

    Raises:
        ValueError: if `meshes` is empty.
    """
    all_corners: list[np.ndarray] = [world_bbox_corners(m) for m in meshes]
    if not all_corners:
        raise ValueError("scene_world_aabb requires at least one mesh")

    stacked = np.vstack(all_corners)
    return AABB(
        min_x=float(stacked[:, 0].min()),
        min_y=float(stacked[:, 1].min()),
        min_z=float(stacked[:, 2].min()),
        max_x=float(stacked[:, 0].max()),
        max_y=float(stacked[:, 1].max()),
        max_z=float(stacked[:, 2].max()),
    )
