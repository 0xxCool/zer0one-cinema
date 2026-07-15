"""Tests for the thin caliper_filter + rolling_axis wrappers.

These modules delegate to WheelGroup fields that are populated inside
`wheel_detect`. The wrappers themselves are trivial — the tests verify
they correctly expose the underlying data.
"""

from __future__ import annotations

from zer0one_cinema.model_prep.caliper_filter import (
    filter_all_static,
    filter_static_from_wheel,
)
from zer0one_cinema.model_prep.rolling_axis import infer_rolling_axis
from zer0one_cinema.model_prep.wheel_detect import WheelGroup


def _make_wheel(
    static_meshes: tuple = (),
    rolling: tuple[float, float, float] = (0.0, 1.0, 0.0),
    label: str = "FL",
) -> WheelGroup:
    return WheelGroup(
        meshes=(),
        center=(0.0, 0.0, 0.35),
        rolling_axis_vector=rolling,
        radius=0.35,
        label=label,
        static_meshes=static_meshes,
    )


# ---------------------------------------------------------------------------
# caliper_filter
# ---------------------------------------------------------------------------


def test_filter_static_from_wheel_returns_populated_static_meshes() -> None:
    mesh1 = object()
    mesh2 = object()
    wheel = _make_wheel(static_meshes=(mesh1, mesh2))
    result = filter_static_from_wheel(wheel)
    assert list(result) == [mesh1, mesh2]


def test_filter_static_from_wheel_empty() -> None:
    wheel = _make_wheel(static_meshes=())
    assert list(filter_static_from_wheel(wheel)) == []


def test_filter_all_static_across_multiple_wheels() -> None:
    m1, m2, m3 = object(), object(), object()
    wheels = [
        _make_wheel(static_meshes=(m1,), label="FL"),
        _make_wheel(static_meshes=(m2, m3), label="FR"),
        _make_wheel(static_meshes=(), label="RL"),
    ]
    result = filter_all_static(wheels)
    assert result == [m1, m2, m3]


# ---------------------------------------------------------------------------
# rolling_axis
# ---------------------------------------------------------------------------


def test_infer_rolling_axis_returns_wheel_field() -> None:
    wheel = _make_wheel(rolling=(1.0, 0.0, 0.0))
    assert infer_rolling_axis(wheel) == (1.0, 0.0, 0.0)


def test_infer_rolling_axis_preserves_y_up() -> None:
    """Vehicle right-axis is typically Y in world (post-PCA canonicalization)."""
    wheel = _make_wheel(rolling=(0.0, 1.0, 0.0))
    axis = infer_rolling_axis(wheel)
    assert axis == (0.0, 1.0, 0.0)
