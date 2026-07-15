"""Unit tests for ground_anchor — pure numpy, no Blender required.

Reuses `MockMesh` from `test_bbox_utils`. Adds `MockObj` (mutable location)
for the top-level-object protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from tests.unit.test_bbox_utils import MockMesh
from zer0one_cinema.model_prep.ground_anchor import (
    apply_z_shift,
    compute_z_shift,
    ground_anchor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class MockObj:
    """Stand-in for `bpy.types.Object` (top-level Empty or root Mesh)."""

    location: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])


def _make_mesh_at_z(z_center: float, size: float = 1.0) -> MockMesh:
    """Mesh with local bbox = size-cube, world position = (0, 0, z_center)."""
    matrix = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, z_center],
        [0.0, 0.0, 0.0, 1.0],
    ]
    half = size / 2.0
    bbox = [
        [-half, -half, -half],
        [-half, -half, half],
        [-half, half, half],
        [-half, half, -half],
        [half, -half, -half],
        [half, -half, half],
        [half, half, half],
        [half, half, -half],
    ]
    return MockMesh(matrix_world=matrix, bound_box=bbox)


# ---------------------------------------------------------------------------
# compute_z_shift
# ---------------------------------------------------------------------------


def test_compute_z_shift_lifts_sunk_mesh() -> None:
    """Mesh centered at z=-0.5 (bottom at z=-1.0) needs a +1.0 shift."""
    mesh = _make_mesh_at_z(-0.5)
    assert compute_z_shift([mesh]) == pytest.approx(1.0)


def test_compute_z_shift_drops_floating_mesh() -> None:
    """Mesh centered at z=+2.0 (bottom at z=+1.5) needs a -1.5 shift."""
    mesh = _make_mesh_at_z(2.0)
    assert compute_z_shift([mesh]) == pytest.approx(-1.5)


def test_compute_z_shift_zero_when_already_grounded() -> None:
    """Mesh centered at z=+0.5 (bottom at z=0) is already on the floor."""
    mesh = _make_mesh_at_z(0.5)
    assert compute_z_shift([mesh]) == 0.0


def test_compute_z_shift_idempotent_within_epsilon() -> None:
    """Within 1e-6 metres of z=0, we return 0 (idempotent guarantee)."""
    mesh = _make_mesh_at_z(0.5 + 1e-9)  # bottom at z=1e-9 (below epsilon)
    assert compute_z_shift([mesh]) == 0.0


def test_compute_z_shift_rs6_regression() -> None:
    """Reproduces the RS6-v3 numeric case: min_z was -0.0892 in world coords,
    the old sampled-vertices approach missed it and the wheels sank.
    """
    mesh = _make_mesh_at_z(-0.0892 + 0.5)  # bottom at z=-0.0892
    assert compute_z_shift([mesh]) == pytest.approx(0.0892)


# ---------------------------------------------------------------------------
# apply_z_shift
# ---------------------------------------------------------------------------


def test_apply_z_shift_moves_all_objects() -> None:
    objs = [
        MockObj(location=[1.0, 2.0, 3.0]),
        MockObj(location=[0.0, 0.0, 0.0]),
        MockObj(location=[-5.0, -5.0, -5.0]),
    ]
    moved = apply_z_shift(objs, dz=0.5)
    assert moved == 3
    assert objs[0].location == [1.0, 2.0, 3.5]
    assert objs[1].location == [0.0, 0.0, 0.5]
    assert objs[2].location == [-5.0, -5.0, -4.5]


def test_apply_z_shift_no_op_when_dz_zero() -> None:
    obj = MockObj(location=[1.0, 2.0, 3.0])
    moved = apply_z_shift([obj], dz=0.0)
    assert moved == 0
    assert obj.location == [1.0, 2.0, 3.0]


def test_apply_z_shift_preserves_xy() -> None:
    obj = MockObj(location=[1.0, 2.0, 3.0])
    apply_z_shift([obj], dz=100.0)
    assert obj.location[0] == 1.0
    assert obj.location[1] == 2.0


# ---------------------------------------------------------------------------
# ground_anchor (end-to-end)
# ---------------------------------------------------------------------------


def test_ground_anchor_lifts_sunk_scene() -> None:
    mesh = _make_mesh_at_z(-0.089 + 0.5)  # bottom at z=-0.089 (RS6 case)
    obj = MockObj(location=[0.0, 0.0, 0.0])
    report = ground_anchor([mesh], [obj])
    assert report["z_shift"] == pytest.approx(0.089)
    assert report["objects_moved"] == 1
    assert report["idempotent"] is False
    assert obj.location[2] == pytest.approx(0.089)


def test_ground_anchor_no_op_when_already_grounded() -> None:
    mesh = _make_mesh_at_z(0.5)  # bottom exactly at z=0
    obj = MockObj(location=[0.0, 0.0, 0.0])
    report = ground_anchor([mesh], [obj])
    assert report["idempotent"] is True
    assert report["z_shift"] == 0.0
    assert report["objects_moved"] == 0


def test_ground_anchor_double_run_is_stable() -> None:
    """Running twice yields the same final state as running once."""
    mesh = _make_mesh_at_z(-0.089 + 0.5)
    obj_1 = MockObj(location=[0.0, 0.0, 0.0])
    obj_2 = MockObj(location=[0.0, 0.0, 0.0])
    ground_anchor([mesh], [obj_1])
    # For run 2: we simulate a re-loaded scene where bottom is now at z=0
    grounded_mesh = _make_mesh_at_z(0.5)
    ground_anchor([grounded_mesh], [obj_2])
    # Both obj should be at z=0.089 (moved once) — never double-shifted
    assert obj_1.location[2] == pytest.approx(0.089)
    assert obj_2.location[2] == 0.0


def test_ground_anchor_returns_scene_aabb_provenance() -> None:
    mesh = _make_mesh_at_z(-0.5)
    obj = MockObj(location=[0.0, 0.0, 0.0])
    report = ground_anchor([mesh], [obj])
    # AABB before shift: mesh centered at z=-0.5 → bottom -1.0, top 0.0
    assert report["scene_aabb_before"][2] == pytest.approx(-1.0)  # min_z
    assert report["scene_aabb_before"][5] == pytest.approx(0.0)  # max_z
