"""Unit tests for origin_fix — pure-python mocks, no Blender needed."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from zer0one_cinema.model_prep.origin_fix import (
    set_origin_to_center,
    set_wheel_origins_to_center,
)
from zer0one_cinema.model_prep.wheel_detect import WheelGroup

# ---------------------------------------------------------------------------
# Mock infrastructure — mesh with mutable vertex list + mutable location
# ---------------------------------------------------------------------------


@dataclass
class MockVertex:
    """A single vertex with a mutable 3-vector coord."""

    co: list[float]


@dataclass
class MockVertexData:
    vertices: list[MockVertex] = field(default_factory=list)


@dataclass
class MockObject:
    """A stand-in for bpy.types.Object with mutable location + mesh data."""

    name: str
    location: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    data: MockVertexData = field(default_factory=MockVertexData)


def _make_wheel_object(
    name: str,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
    vertices_world: list[tuple[float, float, float]] | None = None,
) -> MockObject:
    """Create a MockObject whose vertices are in world coords minus the object origin."""
    if vertices_world is None:
        vertices_world = [(0.0, 0.0, 0.0)]
    verts = [
        MockVertex(co=[vx - origin[0], vy - origin[1], vz - origin[2]])
        for vx, vy, vz in vertices_world
    ]
    return MockObject(
        name=name,
        location=list(origin),
        data=MockVertexData(vertices=verts),
    )


def _make_wheel_group(
    label: str,
    center: tuple[float, float, float],
    meshes: list[MockObject],
    static_meshes: list[MockObject] | None = None,
) -> WheelGroup:
    return WheelGroup(
        meshes=tuple(meshes),  # type: ignore[arg-type]
        center=center,
        rolling_axis_vector=(0.0, 1.0, 0.0),
        radius=0.35,
        label=label,
        static_meshes=tuple(static_meshes or ()),  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# set_origin_to_center
# ---------------------------------------------------------------------------


def test_set_origin_moves_object_and_returns_record() -> None:
    """Moving origin from (0,0,0) to (1,0,0.35) — vertices shift by (-1,0,-0.35)."""
    obj = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0), vertices_world=[(0.5, 0.5, 0.5)])
    rec = set_origin_to_center(obj, (1.0, 0.0, 0.35))
    assert rec is not None
    assert rec.new_location == pytest.approx((1.0, 0.0, 0.35))
    assert obj.location == pytest.approx([1.0, 0.0, 0.35])
    # Vertex was at local (0.5, 0.5, 0.5) with origin (0,0,0) → world (0.5, 0.5, 0.5)
    # After: origin moves to (1, 0, 0.35), vertex must still be at world (0.5, 0.5, 0.5)
    # → local becomes (0.5 - 1.0, 0.5 - 0.0, 0.5 - 0.35) = (-0.5, 0.5, 0.15)
    v = obj.data.vertices[0]
    assert v.co == pytest.approx([-0.5, 0.5, 0.15])


def test_set_origin_no_op_when_already_centered() -> None:
    """Origin already within 1 mm of target → return None, no vertex shift."""
    obj = _make_wheel_object(
        "wheel_FL",
        origin=(1.0, 0.0, 0.35),
        vertices_world=[(1.5, 0.5, 0.85)],
    )
    # Snapshot vertex before
    original_co = list(obj.data.vertices[0].co)
    rec = set_origin_to_center(obj, (1.0, 0.0, 0.35))
    assert rec is None
    assert obj.data.vertices[0].co == original_co  # unchanged
    assert obj.location == [1.0, 0.0, 0.35]


def test_set_origin_no_op_below_1mm() -> None:
    """A 0.5mm difference is below the tolerance — no-op."""
    obj = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0), vertices_world=[(0.5, 0.5, 0.5)])
    rec = set_origin_to_center(obj, (0.0, 0.0, 0.0005))  # 0.5mm on z
    assert rec is None


def test_set_origin_preserves_world_position() -> None:
    """Cardinal invariant: after re-origin, vertex world-position is unchanged."""
    world_pos = (2.0, 3.0, 4.0)
    obj = _make_wheel_object("vertex_test", origin=(0.0, 0.0, 0.0), vertices_world=[world_pos])
    set_origin_to_center(obj, (1.0, 0.0, 0.35))
    v = obj.data.vertices[0]
    new_world_x = v.co[0] + obj.location[0]
    new_world_y = v.co[1] + obj.location[1]
    new_world_z = v.co[2] + obj.location[2]
    assert (new_world_x, new_world_y, new_world_z) == pytest.approx(world_pos)


def test_set_origin_reports_delta_magnitude() -> None:
    obj = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0))
    rec = set_origin_to_center(obj, (3.0, 4.0, 0.0))
    assert rec is not None
    assert rec.delta_meters == pytest.approx(5.0)  # 3-4-5 triangle


# ---------------------------------------------------------------------------
# set_wheel_origins_to_center
# ---------------------------------------------------------------------------


def test_set_wheel_origins_moves_all_4_wheels() -> None:
    fl = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0))
    fr = _make_wheel_object("wheel_FR", origin=(0.0, 0.0, 0.0))
    rl = _make_wheel_object("wheel_RL", origin=(0.0, 0.0, 0.0))
    rr = _make_wheel_object("wheel_RR", origin=(0.0, 0.0, 0.0))
    wheels = [
        _make_wheel_group("FL", (1.35, -0.8, 0.35), [fl]),
        _make_wheel_group("FR", (1.35, +0.8, 0.35), [fr]),
        _make_wheel_group("RL", (-1.35, -0.8, 0.35), [rl]),
        _make_wheel_group("RR", (-1.35, +0.8, 0.35), [rr]),
    ]
    report = set_wheel_origins_to_center(wheels)
    assert report.origins_moved == 4
    assert report.skipped_already_centered == 0
    # Each object.location matches its wheel.center
    assert fl.location == pytest.approx([1.35, -0.8, 0.35])
    assert fr.location == pytest.approx([1.35, 0.8, 0.35])
    assert rl.location == pytest.approx([-1.35, -0.8, 0.35])
    assert rr.location == pytest.approx([-1.35, 0.8, 0.35])


def test_set_wheel_origins_skips_static_meshes() -> None:
    """Static caliper meshes MUST NOT be re-origined — else they'd rotate with wheel."""
    rim = _make_wheel_object("rim_FL", origin=(0.0, 0.0, 0.0))
    caliper = _make_wheel_object("caliper_FL", origin=(0.0, 0.0, 0.0))
    wheel = _make_wheel_group(
        "FL",
        center=(1.0, 0.0, 0.35),
        meshes=[rim],
        static_meshes=[caliper],
    )
    set_wheel_origins_to_center([wheel])
    # Rim was moved to wheel center
    assert rim.location == pytest.approx([1.0, 0.0, 0.35])
    # Caliper untouched
    assert caliper.location == [0.0, 0.0, 0.0]


def test_set_wheel_origins_idempotent() -> None:
    obj = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0))
    wheel = _make_wheel_group("FL", (1.0, 0.0, 0.35), [obj])
    r1 = set_wheel_origins_to_center([wheel])
    r2 = set_wheel_origins_to_center([wheel])
    assert r1.origins_moved == 1
    assert r2.origins_moved == 0
    assert r2.skipped_already_centered == 1


def test_set_wheel_origins_report_has_per_wheel_records() -> None:
    obj = _make_wheel_object("wheel_FL", origin=(0.0, 0.0, 0.0))
    wheel = _make_wheel_group("FL", (1.0, 0.0, 0.35), [obj])
    report = set_wheel_origins_to_center([wheel])
    assert "FL" in report.per_wheel
    assert len(report.per_wheel["FL"]) == 1
    rec = report.per_wheel["FL"][0]
    assert rec.object_name == "wheel_FL"


def test_set_wheel_origins_empty_input() -> None:
    """No wheels → empty report."""
    report = set_wheel_origins_to_center([])
    assert report.origins_moved == 0
    assert report.skipped_already_centered == 0
    assert report.per_wheel == {}
