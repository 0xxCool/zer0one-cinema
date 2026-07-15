"""Unit tests for bbox_utils — pure numpy, no Blender required.

Uses `MockMesh` (a dataclass) as a stand-in for `bpy.types.Object` (mesh).
The `MeshLike` protocol lets our production code accept either.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pytest

from zer0one_cinema.model_prep.bbox_utils import (
    AABB,
    scene_world_aabb,
    world_bbox_corners,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class MockMesh:
    """Stand-in for a Blender mesh object, satisfying `MeshLike`."""

    matrix_world: Sequence[Sequence[float]]
    bound_box: Sequence[Sequence[float]]


IDENTITY_4X4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]

# Unit cube corners (Blender's own convention: 8 corners in a fixed order)
UNIT_CUBE_CORNERS = [
    [-0.5, -0.5, -0.5],
    [-0.5, -0.5, 0.5],
    [-0.5, 0.5, 0.5],
    [-0.5, 0.5, -0.5],
    [0.5, -0.5, -0.5],
    [0.5, -0.5, 0.5],
    [0.5, 0.5, 0.5],
    [0.5, 0.5, -0.5],
]


def _translation_matrix(x: float, y: float, z: float) -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, x],
        [0.0, 1.0, 0.0, y],
        [0.0, 0.0, 1.0, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


# ---------------------------------------------------------------------------
# world_bbox_corners
# ---------------------------------------------------------------------------


def test_world_bbox_corners_identity_leaves_local() -> None:
    mesh = MockMesh(matrix_world=IDENTITY_4X4, bound_box=UNIT_CUBE_CORNERS)
    result = world_bbox_corners(mesh)
    np.testing.assert_allclose(result, UNIT_CUBE_CORNERS)


def test_world_bbox_corners_translation_shifts_all_corners() -> None:
    mesh = MockMesh(matrix_world=_translation_matrix(10, 20, 30), bound_box=UNIT_CUBE_CORNERS)
    result = world_bbox_corners(mesh)
    expected = np.asarray(UNIT_CUBE_CORNERS) + np.array([10, 20, 30])
    np.testing.assert_allclose(result, expected)


def test_world_bbox_corners_returns_shape_8x3() -> None:
    mesh = MockMesh(matrix_world=IDENTITY_4X4, bound_box=UNIT_CUBE_CORNERS)
    assert world_bbox_corners(mesh).shape == (8, 3)


def test_world_bbox_corners_returns_float64() -> None:
    mesh = MockMesh(matrix_world=IDENTITY_4X4, bound_box=UNIT_CUBE_CORNERS)
    assert world_bbox_corners(mesh).dtype == np.float64


def test_world_bbox_corners_rejects_wrong_matrix_shape() -> None:
    mesh = MockMesh(matrix_world=[[1, 0], [0, 1]], bound_box=UNIT_CUBE_CORNERS)
    with pytest.raises(ValueError, match="4x4"):
        world_bbox_corners(mesh)


def test_world_bbox_corners_rejects_wrong_bbox_shape() -> None:
    mesh = MockMesh(matrix_world=IDENTITY_4X4, bound_box=[[0, 0, 0]])
    with pytest.raises(ValueError, match=r"\(8, 3\)"):
        world_bbox_corners(mesh)


# ---------------------------------------------------------------------------
# scene_world_aabb
# ---------------------------------------------------------------------------


def test_scene_aabb_single_unit_cube_at_origin() -> None:
    mesh = MockMesh(matrix_world=IDENTITY_4X4, bound_box=UNIT_CUBE_CORNERS)
    aabb = scene_world_aabb([mesh])
    assert aabb == AABB(-0.5, -0.5, -0.5, 0.5, 0.5, 0.5)


def test_scene_aabb_two_meshes_translated() -> None:
    m1 = MockMesh(matrix_world=IDENTITY_4X4, bound_box=UNIT_CUBE_CORNERS)
    m2 = MockMesh(matrix_world=_translation_matrix(5, 0, 0), bound_box=UNIT_CUBE_CORNERS)
    aabb = scene_world_aabb([m1, m2])
    # m1: x ∈ [-0.5, 0.5]; m2: x ∈ [4.5, 5.5]; combined: [-0.5, 5.5]
    assert aabb.min_x == -0.5
    assert aabb.max_x == 5.5
    assert aabb.min_y == -0.5
    assert aabb.max_y == 0.5


def test_scene_aabb_min_z_from_lowest_mesh() -> None:
    """Regression: the RS6-v3 bug was that we sampled only some meshes, so a
    low-hanging mesh was missed and its wheels sank below the plane.
    """
    high_mesh = MockMesh(matrix_world=_translation_matrix(0, 0, 2), bound_box=UNIT_CUBE_CORNERS)
    low_mesh = MockMesh(matrix_world=_translation_matrix(0, 0, -1), bound_box=UNIT_CUBE_CORNERS)
    aabb = scene_world_aabb([high_mesh, low_mesh])
    # low_mesh: z ∈ [-1.5, -0.5]; overall min_z must be -1.5
    assert aabb.min_z == -1.5
    assert aabb.max_z == 2.5


def test_scene_aabb_empty_raises() -> None:
    with pytest.raises(ValueError, match="at least one mesh"):
        scene_world_aabb([])


def test_aabb_size_and_center() -> None:
    aabb = AABB(-1.0, -2.0, -3.0, 1.0, 2.0, 3.0)
    assert aabb.size == (2.0, 4.0, 6.0)
    assert aabb.center == (0.0, 0.0, 0.0)


def test_aabb_frozen() -> None:
    """AABB must be immutable (frozen dataclass)."""
    aabb = AABB(0, 0, 0, 1, 1, 1)
    with pytest.raises(Exception):  # FrozenInstanceError from dataclasses
        aabb.min_x = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Determinism (same input → identical output, bit-for-bit)
# ---------------------------------------------------------------------------


def test_scene_aabb_deterministic() -> None:
    meshes_1 = [
        MockMesh(matrix_world=_translation_matrix(i, 0, 0), bound_box=UNIT_CUBE_CORNERS)
        for i in range(10)
    ]
    meshes_2 = [
        MockMesh(matrix_world=_translation_matrix(i, 0, 0), bound_box=UNIT_CUBE_CORNERS)
        for i in range(10)
    ]
    assert scene_world_aabb(meshes_1) == scene_world_aabb(meshes_2)
