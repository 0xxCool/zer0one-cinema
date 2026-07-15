"""Unit tests for body_group — pure-python mocks, no Blender needed."""

from __future__ import annotations

import pytest

from tests.unit.test_bbox_utils import MockMesh
from zer0one_cinema.model_prep.body_group import BodyGroupError, build_body_group
from zer0one_cinema.model_prep.wheel_detect import WheelGroup


def _make_box_mesh(
    center: tuple[float, float, float],
    size: tuple[float, float, float],
) -> MockMesh:
    """Box mesh at world-space `center` with given size (via matrix_world translation)."""
    cx, cy, cz = center
    sx, sy, sz = size
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    matrix = [
        [1.0, 0.0, 0.0, cx],
        [0.0, 1.0, 0.0, cy],
        [0.0, 0.0, 1.0, cz],
        [0.0, 0.0, 0.0, 1.0],
    ]
    bbox_local = [
        [-hx, -hy, -hz],
        [-hx, -hy, hz],
        [-hx, hy, hz],
        [-hx, hy, -hz],
        [hx, -hy, -hz],
        [hx, -hy, hz],
        [hx, hy, hz],
        [hx, hy, -hz],
    ]
    return MockMesh(matrix_world=matrix, bound_box=bbox_local)


def _make_wheel_group_from(
    meshes: list[MockMesh],
    static: list[MockMesh] | None = None,
    center: tuple[float, float, float] = (0.0, 0.0, 0.35),
    label: str = "FL",
) -> WheelGroup:
    return WheelGroup(
        meshes=tuple(meshes),  # type: ignore[arg-type]
        center=center,
        rolling_axis_vector=(0.0, 1.0, 0.0),
        radius=0.35,
        label=label,
        static_meshes=tuple(static or ()),  # type: ignore[arg-type]
    )


def _make_four_wheels() -> list[WheelGroup]:
    """Return 4 empty wheel-groups at realistic car positions (wheelbase 2.7, track 1.6)."""
    return [
        _make_wheel_group_from([], center=(1.35, -0.8, 0.35), label="FL"),
        _make_wheel_group_from([], center=(1.35, 0.8, 0.35), label="FR"),
        _make_wheel_group_from([], center=(-1.35, -0.8, 0.35), label="RL"),
        _make_wheel_group_from([], center=(-1.35, 0.8, 0.35), label="RR"),
    ]


# ---------------------------------------------------------------------------
# Basic body-group construction
# ---------------------------------------------------------------------------


def test_body_group_excludes_wheel_meshes() -> None:
    body = _make_box_mesh(center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4))
    wheel_rim = _make_box_mesh(center=(1.35, -0.8, 0.35), size=(0.7, 0.22, 0.7))
    all_meshes = [body, wheel_rim]
    wheels = [_make_wheel_group_from([wheel_rim])]
    result = build_body_group(all_meshes, wheels)
    assert body in result.meshes
    assert wheel_rim not in result.meshes
    assert result.excluded_wheel_meshes == 1


def test_body_group_excludes_static_wheel_meshes() -> None:
    """Caliper (in wheel.static_meshes) must NOT be counted as body."""
    body = _make_box_mesh(center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4))
    caliper = _make_box_mesh(center=(1.35, -0.75, 0.35), size=(0.15, 0.10, 0.10))
    all_meshes = [body, caliper]
    wheels = [_make_wheel_group_from(meshes=[], static=[caliper])]
    result = build_body_group(all_meshes, wheels)
    assert body in result.meshes
    assert caliper not in result.meshes
    assert result.excluded_wheel_meshes == 1


def test_body_group_excludes_env_by_bbox_diagonal() -> None:
    """A sky-sphere with 100× vehicle diagonal → classified as env.

    Provide 4 wheels so the env-filter has a car-scale wheelbase reference
    (~3 m diagonal), against which the body (~5 m) is inside and the sky
    (~866 m) is way outside.
    """
    body = _make_box_mesh(center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4))
    sky = _make_box_mesh(center=(0.0, 0.0, 0.0), size=(500.0, 500.0, 500.0))
    all_meshes = [body, sky]
    result = build_body_group(all_meshes, wheels=_make_four_wheels())
    assert body in result.meshes
    assert sky not in result.meshes
    assert result.excluded_env_meshes == 1


def test_body_group_excludes_env_by_distance() -> None:
    """A small mesh very far from the vehicle → classified as env."""
    body = _make_box_mesh(center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4))
    far_prop = _make_box_mesh(center=(500.0, 500.0, 500.0), size=(0.5, 0.5, 0.5))
    all_meshes = [body, far_prop]
    result = build_body_group(all_meshes, wheels=_make_four_wheels())
    assert body in result.meshes
    assert far_prop not in result.meshes
    assert result.excluded_env_meshes == 1


def test_body_group_centroid_is_mean_of_body_bbox_centers() -> None:
    m1 = _make_box_mesh(center=(1.0, 0.0, 0.5), size=(0.5, 0.5, 0.5))
    m2 = _make_box_mesh(center=(-1.0, 0.0, 0.5), size=(0.5, 0.5, 0.5))
    result = build_body_group([m1, m2], wheels=[])
    # Centroid = mean of (1, 0, 0.5) and (-1, 0, 0.5) = (0, 0, 0.5)
    assert result.centroid == pytest.approx((0.0, 0.0, 0.5))


def test_body_group_bbox_encloses_all_body_meshes() -> None:
    m1 = _make_box_mesh(center=(2.0, 0.0, 0.5), size=(1.0, 1.0, 1.0))
    m2 = _make_box_mesh(center=(-2.0, 0.0, 0.5), size=(1.0, 1.0, 1.0))
    result = build_body_group([m1, m2], wheels=[])
    # m1: x ∈ [1.5, 2.5]; m2: x ∈ [-2.5, -1.5]; combined [-2.5, 2.5]
    assert result.bbox.min_x == pytest.approx(-2.5)
    assert result.bbox.max_x == pytest.approx(2.5)


def test_body_group_raises_on_empty() -> None:
    with pytest.raises(BodyGroupError, match="no meshes given"):
        build_body_group([], wheels=[])


def test_body_group_raises_when_only_wheels() -> None:
    """A scene that's ONLY wheels (no body) → error, since we can't rig the car."""
    wheel = _make_box_mesh(center=(1.35, -0.8, 0.35), size=(0.7, 0.22, 0.7))
    with pytest.raises(BodyGroupError, match="no body meshes"):
        build_body_group([wheel], wheels=[_make_wheel_group_from([wheel])])


def test_body_group_counts_reported() -> None:
    body = _make_box_mesh(center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4))
    wheel = _make_box_mesh(center=(1.35, -0.8, 0.35), size=(0.7, 0.22, 0.7))
    sky = _make_box_mesh(center=(0.0, 0.0, 0.0), size=(500.0, 500.0, 500.0))
    # Provide 4 wheels so env-filter is active
    wheels = _make_four_wheels()
    # Register the wheel mesh with the FL wheel
    wheels[0] = _make_wheel_group_from([wheel], center=(1.35, -0.8, 0.35), label="FL")
    result = build_body_group([body, wheel, sky], wheels=wheels)
    assert result.excluded_wheel_meshes == 1
    assert result.excluded_env_meshes == 1
    assert body in result.meshes
