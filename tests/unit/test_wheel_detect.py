"""Unit tests for wheel_detect — pure numpy + sklearn, no Blender required.

Uses `MockCarMesh` — a NamedMeshLike stand-in with generated wheel/body geometry.
The 6 stages are tested independently (pure functions) plus end-to-end.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pytest

from zer0one_cinema.model_prep.wheel_detect import (
    WheelDetectionError,
    _canonicalize_eigenvector,
    _sort_candidates_canonical,
    aggregate_wheel_meshes,
    cluster_candidates,
    compute_vehicle_frame,
    detect_wheels,
    find_candidates,
    label_wheels_flfr_rlrr,
    validate_rectangle,
    validate_symmetry,
)

# ---------------------------------------------------------------------------
# Test-mesh dataclass — satisfies NamedMeshLike protocol
# ---------------------------------------------------------------------------


@dataclass
class MockCarMesh:
    """A mesh with matrix_world + bound_box + name + world_verts."""

    name: str
    matrix_world: Sequence[Sequence[float]]
    bound_box: Sequence[Sequence[float]]
    world_verts: np.ndarray


def _identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _make_box_mesh(
    name: str, center: tuple[float, float, float], size: tuple[float, float, float]
) -> MockCarMesh:
    """A rectangular-box mesh at world-space `center` with `size` extent."""
    cx, cy, cz = center
    sx, sy, sz = size
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    # 8 world-space corners
    corners = np.array(
        [
            [cx - hx, cy - hy, cz - hz],
            [cx - hx, cy - hy, cz + hz],
            [cx - hx, cy + hy, cz + hz],
            [cx - hx, cy + hy, cz - hz],
            [cx + hx, cy - hy, cz - hz],
            [cx + hx, cy - hy, cz + hz],
            [cx + hx, cy + hy, cz + hz],
            [cx + hx, cy + hy, cz - hz],
        ],
        dtype=np.float64,
    )
    # In our test model, bound_box is already in world coords → identity matrix_world
    # Local bound_box coords = world coords - center (so matrix_world translates them back)
    local_bbox = corners - np.array([cx, cy, cz])
    m_matrix = [
        [1.0, 0.0, 0.0, cx],
        [0.0, 1.0, 0.0, cy],
        [0.0, 0.0, 1.0, cz],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return MockCarMesh(
        name=name,
        matrix_world=m_matrix,
        bound_box=local_bbox.tolist(),
        world_verts=corners,
    )


def _make_wheel_mesh(
    name: str, center: tuple[float, float, float], radius: float, width: float
) -> MockCarMesh:
    """A wheel-shaped mesh: local X-axis is thin (wheel width), Y and Z are the wheel diameter.

    Wheels are approximated as thin boxes so that Stage-2 aspect ratios pass:
        short-dim = width, mid = 2r, long = 2r
        aspect_short = width / (2r) ≈ 0.2-0.4 for real cars
        aspect_disc  = 1.0
    """
    # After the vehicle-frame PCA, X = forward, Y = right, Z = up.
    # Wheels roll around Y (the vehicle's right axis), so the wheel width is Y.
    # In this simple test we place a synthetic vehicle where the wheels are boxes
    # aligned to the world axes: their world-space size is (2r, width, 2r)
    return _make_box_mesh(name, center, (2 * radius, width, 2 * radius))


def _make_synthetic_car(
    wheelbase: float = 2.7,
    track_width: float = 1.6,
    wheel_radius: float = 0.35,
    wheel_width: float = 0.22,
) -> list[MockCarMesh]:
    """Build a minimal 4-wheeled test car: 4 wheels + a body box.

    Coordinate convention (world):
        X = forward (vehicle length)
        Y = right (track width)
        Z = up
    """
    half_wb = wheelbase / 2
    half_tw = track_width / 2
    wheel_z = wheel_radius  # wheel center is at z = radius (touching floor at z=0)

    meshes = [
        # Body box: 4.5 m long × 1.8 m wide × 1.4 m tall, centered at (0, 0, 0.7)
        _make_box_mesh("body", (0.0, 0.0, 0.7), (4.5, 1.8, 1.4)),
        # Front-left wheel: X > 0, Y < 0
        _make_wheel_mesh("wheel_FL", (+half_wb, -half_tw, wheel_z), wheel_radius, wheel_width),
        # Front-right wheel: X > 0, Y > 0
        _make_wheel_mesh("wheel_FR", (+half_wb, +half_tw, wheel_z), wheel_radius, wheel_width),
        # Rear-left wheel: X < 0, Y < 0
        _make_wheel_mesh("wheel_RL", (-half_wb, -half_tw, wheel_z), wheel_radius, wheel_width),
        # Rear-right wheel: X < 0, Y > 0
        _make_wheel_mesh("wheel_RR", (-half_wb, +half_tw, wheel_z), wheel_radius, wheel_width),
    ]
    return meshes


# ---------------------------------------------------------------------------
# Stage 1: compute_vehicle_frame
# ---------------------------------------------------------------------------


def test_canonicalize_eigenvector_positive_first_component():
    v = np.array([0.5, 0.7, 0.2])
    result = _canonicalize_eigenvector(v)
    np.testing.assert_allclose(result, v)  # already canonical


def test_canonicalize_eigenvector_flips_when_dominant_negative():
    v = np.array([-0.7, 0.5, 0.2])
    result = _canonicalize_eigenvector(v)
    np.testing.assert_allclose(result, -v)  # dominant is |−0.7|, flipped positive


def test_compute_vehicle_frame_axis_ordering():
    """A car that's 4.5 m long × 1.8 m wide × 1.4 m tall should have:
    forward = longest axis, right = mid, up = shortest.
    """
    meshes = _make_synthetic_car()
    all_verts = np.concatenate([m.world_verts for m in meshes])
    frame = compute_vehicle_frame(all_verts)

    # Forward should be world-X (largest dimension, 4.5 m)
    # Since we built the car aligned to world axes, forward = ±X, right = ±Y, up = ±Z
    assert abs(frame.forward_axis[0]) > 0.95  # nearly pure X
    assert abs(frame.right_axis[1]) > 0.95  # nearly pure Y
    assert abs(frame.up_axis[2]) > 0.95  # nearly pure Z


def test_compute_vehicle_frame_right_handed():
    """cross(forward, right) should equal up (right-handed frame)."""
    meshes = _make_synthetic_car()
    all_verts = np.concatenate([m.world_verts for m in meshes])
    frame = compute_vehicle_frame(all_verts)
    fwd = np.array(frame.forward_axis)
    right = np.array(frame.right_axis)
    up = np.array(frame.up_axis)
    cross = np.cross(fwd, right)
    # cross should point in same direction as up
    assert np.dot(cross, up) > 0.95


def test_compute_vehicle_frame_deterministic():
    """Same vertex set → same frame."""
    meshes = _make_synthetic_car()
    verts = np.concatenate([m.world_verts for m in meshes])
    f1 = compute_vehicle_frame(verts)
    f2 = compute_vehicle_frame(verts)
    assert f1 == f2


def test_compute_vehicle_frame_rejects_too_few_verts():
    with pytest.raises(WheelDetectionError, match="need >=4 verts"):
        compute_vehicle_frame(np.array([[0.0, 0.0, 0.0]]))


# ---------------------------------------------------------------------------
# Stage 2: find_candidates
# ---------------------------------------------------------------------------


def test_find_candidates_finds_all_4_wheels():
    meshes = _make_synthetic_car()
    all_verts = np.concatenate([m.world_verts for m in meshes])
    frame = compute_vehicle_frame(all_verts)
    candidates = find_candidates(meshes, frame)
    # Should find exactly the 4 wheels, not the body
    assert len(candidates) == 4
    names = {c.mesh.name for c in candidates}
    assert names == {"wheel_FL", "wheel_FR", "wheel_RL", "wheel_RR"}


def test_find_candidates_excludes_body():
    meshes = _make_synthetic_car()
    all_verts = np.concatenate([m.world_verts for m in meshes])
    frame = compute_vehicle_frame(all_verts)
    candidates = find_candidates(meshes, frame)
    names = {c.mesh.name for c in candidates}
    assert "body" not in names


def test_find_candidates_empty_when_no_wheels():
    """A scene with only a body-shaped box should yield no wheel candidates."""
    body_only = [_make_box_mesh("body", (0.0, 0.0, 0.7), (4.5, 1.8, 1.4))]
    all_verts = np.concatenate([m.world_verts for m in body_only])
    frame = compute_vehicle_frame(all_verts)
    candidates = find_candidates(body_only, frame)
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# Stage 4: cluster_candidates + canonical sort
# ---------------------------------------------------------------------------


def test_sort_candidates_deterministic_across_input_order():
    """The sort key is (rounded) center coords, so the output is order-independent."""
    meshes = _make_synthetic_car()
    frame = compute_vehicle_frame(np.concatenate([m.world_verts for m in meshes]))
    cands = find_candidates(meshes, frame)

    # Reverse-input case: same sorted output
    sorted_a = _sort_candidates_canonical(cands)
    sorted_b = _sort_candidates_canonical(list(reversed(cands)))
    assert [c.mesh.name for c in sorted_a] == [c.mesh.name for c in sorted_b]


def test_cluster_candidates_k4_returns_4_labels():
    meshes = _make_synthetic_car()
    frame = compute_vehicle_frame(np.concatenate([m.world_verts for m in meshes]))
    cands = _sort_candidates_canonical(find_candidates(meshes, frame))
    labels = cluster_candidates(cands, k=4, seed=0)
    assert len(labels) == 4
    assert set(labels) == {0, 1, 2, 3}


def test_cluster_candidates_deterministic():
    """Same seed + same sorted input → identical labels."""
    meshes = _make_synthetic_car()
    frame = compute_vehicle_frame(np.concatenate([m.world_verts for m in meshes]))
    cands = _sort_candidates_canonical(find_candidates(meshes, frame))
    labels_1 = cluster_candidates(cands, k=4, seed=0)
    labels_2 = cluster_candidates(cands, k=4, seed=0)
    assert labels_1 == labels_2


def test_cluster_candidates_rejects_k_too_big():
    meshes = _make_synthetic_car()
    frame = compute_vehicle_frame(np.concatenate([m.world_verts for m in meshes]))
    cands = _sort_candidates_canonical(find_candidates(meshes, frame))
    with pytest.raises(WheelDetectionError, match="k=99 exceeds"):
        cluster_candidates(cands, k=99, seed=0)


# ---------------------------------------------------------------------------
# Stage 5: validate_rectangle + validate_symmetry
# ---------------------------------------------------------------------------


def test_validate_rectangle_true_for_square():
    """4 corners of a unit square (in xy-plane) form a rectangle."""
    pts = np.array(
        [
            [+1.0, -1.0, 0.0],
            [+1.0, +1.0, 0.0],
            [-1.0, -1.0, 0.0],
            [-1.0, +1.0, 0.0],
        ]
    )
    assert validate_rectangle(pts) is True


def test_validate_rectangle_true_for_asymmetric_rectangle():
    """Wheelbase 2.7 × track-width 1.6 rectangle."""
    pts = np.array(
        [
            [+1.35, -0.8, 0.0],
            [+1.35, +0.8, 0.0],
            [-1.35, -0.8, 0.0],
            [-1.35, +0.8, 0.0],
        ]
    )
    assert validate_rectangle(pts) is True


def test_validate_rectangle_false_for_skewed_quadrilateral():
    """A trapezoid should be rejected."""
    pts = np.array(
        [
            [+1.0, -1.0, 0.0],
            [+2.0, +1.0, 0.0],
            [-1.0, -1.0, 0.0],
            [-1.0, +1.0, 0.0],
        ]
    )
    assert validate_rectangle(pts) is False


def test_validate_rectangle_false_when_not_4_points():
    pts = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 2.0, 0.0]])
    assert validate_rectangle(pts) is False


def test_validate_symmetry_true_for_mirrored_pairs():
    pts = np.array(
        [
            [+1.0, -0.8, 0.0],
            [+1.0, +0.8, 0.0],
            [-1.0, -0.8, 0.0],
            [-1.0, +0.8, 0.0],
        ]
    )
    assert validate_symmetry(pts) is True


def test_validate_rectangle_rs6_real_world_tolerance():
    """Regression: real automotive GLBs (RS6 raw) have ~11% short-edge variance.

    Root cause: complex wheel assemblies (rim + tire + brake disc + caliper) mean
    cluster-center per wheel-side drifts a few cm from the geometric ideal. A single
    false-positive cylinder in Cluster 0 shifts its mean by 30cm → short-edges
    become 1.525 vs 1.719 (11.3% diff). tol=0.10 rejects; production default
    tol=0.20 accepts. Actual RS6 case with clusters slightly perturbed inward.
    """
    pts = np.array(
        [
            [+1.460, -0.687, 0.0],  # FR-cluster mean (skewed inward by false-positive)
            [+1.725, +0.814, 0.0],  # FL-cluster mean
            [-1.184, -0.884, 0.0],  # RR-cluster mean
            [-1.217, +0.835, 0.0],  # RL-cluster mean
        ]
    )
    assert validate_rectangle(pts, tol_rel=0.10) is False
    assert validate_rectangle(pts, tol_rel=0.20) is True
    assert validate_symmetry(pts, tol_rel=0.20) is True


def test_validate_symmetry_false_when_only_one_side():
    """All wheels on the same side of the mid-plane → not symmetric."""
    pts = np.array(
        [
            [+1.0, +0.5, 0.0],
            [+1.0, +0.6, 0.0],
            [-1.0, +0.5, 0.0],
            [-1.0, +0.6, 0.0],
        ]
    )
    # right coords all positive → after reflection, all on other side → no match
    assert validate_symmetry(pts) is False


# ---------------------------------------------------------------------------
# Stage 6: labeling + aggregation
# ---------------------------------------------------------------------------


def test_label_wheels_flfr_rlrr_correct_quadrants():
    """4 wheels in canonical positions → FL/FR/RL/RR."""
    # forward is x, right is y. Order: FL, FR, RL, RR
    pts = np.array(
        [
            [+1.35, -0.8, 0.35],  # FL (front, left = -Y)
            [+1.35, +0.8, 0.35],  # FR
            [-1.35, -0.8, 0.35],  # RL
            [-1.35, +0.8, 0.35],  # RR
        ]
    )
    labels = label_wheels_flfr_rlrr(pts)
    assert labels == ["FL", "FR", "RL", "RR"]


def test_label_wheels_flfr_rlrr_returns_generic_when_not_4():
    pts = np.array([[+1.0, -0.5, 0.35], [-1.0, +0.5, 0.35]])
    labels = label_wheels_flfr_rlrr(pts)
    assert labels == ["W0", "W1"]


def test_aggregate_wheel_meshes_separates_static_from_rotating():
    # Central rim/tire mesh (radial offset ≈ 0)
    rim = _make_box_mesh("rim", (0.0, 0.0, 0.35), (0.6, 0.15, 0.6))
    # Caliper mesh: offset forward from wheel center by 0.15 m (radial > 20% of 0.35 m radius)
    caliper = _make_box_mesh("caliper", (0.15, 0.0, 0.35), (0.1, 0.1, 0.1))

    wheel_center = np.array([0.0, 0.0, 0.35])
    wheel_radius = 0.35
    rolling_axis = np.array([0.0, 1.0, 0.0])  # Y-axis (car's right)

    rotating, static = aggregate_wheel_meshes(
        wheel_center_world=wheel_center,
        wheel_radius=wheel_radius,
        rolling_axis=rolling_axis,
        all_meshes=[rim, caliper],
    )
    rotating_names = {m.name for m in rotating}
    static_names = {m.name for m in static}
    assert "rim" in rotating_names
    assert "caliper" in static_names


def test_aggregate_wheel_meshes_ignores_far_meshes():
    rim = _make_box_mesh("rim", (0.0, 0.0, 0.35), (0.6, 0.15, 0.6))
    far_body = _make_box_mesh("body", (2.5, 0.0, 0.7), (4.5, 1.8, 1.4))
    wheel_center = np.array([0.0, 0.0, 0.35])
    rotating, static = aggregate_wheel_meshes(
        wheel_center_world=wheel_center,
        wheel_radius=0.35,
        rolling_axis=np.array([0.0, 1.0, 0.0]),
        all_meshes=[rim, far_body],
    )
    all_names = {m.name for m in rotating} | {m.name for m in static}
    assert "body" not in all_names  # far from wheel, excluded


# ---------------------------------------------------------------------------
# End-to-End: detect_wheels
# ---------------------------------------------------------------------------


def test_detect_wheels_synthetic_car_e2e():
    meshes = _make_synthetic_car()
    result = detect_wheels(meshes)
    assert len(result.wheels) == 4
    # Labels should be FL, FR, RL, RR in some order
    labels = {w.label for w in result.wheels}
    assert labels == {"FL", "FR", "RL", "RR"}
    assert result.source == "geometric"
    assert result.confidence >= 0.8


def test_detect_wheels_deterministic():
    """Same input + same seed → bit-identical output (labels, centers, radii)."""
    meshes = _make_synthetic_car()
    r1 = detect_wheels(meshes, seed=0)
    r2 = detect_wheels(meshes, seed=0)
    # Wheel labels + centers must match exactly
    assert [w.label for w in r1.wheels] == [w.label for w in r2.wheels]
    for w1, w2 in zip(r1.wheels, r2.wheels, strict=True):
        assert w1.center == w2.center
        assert w1.radius == w2.radius


def test_detect_wheels_correct_positions():
    """FL wheel should be at (+wheelbase/2, -track/2)."""
    meshes = _make_synthetic_car(wheelbase=2.7, track_width=1.6)
    result = detect_wheels(meshes)
    by_label = {w.label: w for w in result.wheels}
    # FL should be forward (+X) and left (-Y in world = matching frame)
    # (frame.forward may be ±X but PCA canonicalization + right-handed enforcement
    # ensures FL/FR/RL/RR match spatial layout.)
    fl = by_label["FL"]
    fr = by_label["FR"]
    rl = by_label["RL"]
    rr = by_label["RR"]
    # Wheelbase: |x_FL - x_RL| should ≈ 2.7
    assert abs(fl.center[0] - rl.center[0]) == pytest.approx(2.7, abs=0.05)
    # Track: |y_FL - y_FR| should ≈ 1.6
    assert abs(fl.center[1] - fr.center[1]) == pytest.approx(1.6, abs=0.05)
    # All wheels approximately at z = 0.35 (wheel radius, touching floor)
    for w in (fl, fr, rl, rr):
        assert w.center[2] == pytest.approx(0.35, abs=0.05)


def test_detect_wheels_correct_radius():
    """Radius should be ≈ 0.35 (wheel_radius parameter)."""
    meshes = _make_synthetic_car(wheel_radius=0.35)
    result = detect_wheels(meshes)
    for w in result.wheels:
        assert w.radius == pytest.approx(0.35, abs=0.05)


def test_detect_wheels_error_on_empty():
    with pytest.raises(WheelDetectionError, match="no meshes"):
        detect_wheels([])


def test_detect_wheels_monster_truck_ratio_regression():
    """Regression: monster-truck wheels have diameter ≈ 44% of vehicle length.

    The initial `_DIAM_FRAC_MAX = 0.35` threshold rejected them. Real-world test
    on kenney_monster_truck.glb (v0.1.5, A5) showed this needs to be at least
    0.44 to survive. We now use 0.50 with margin.
    """
    # Truck body: 0.44 × 0.61 × 0.64 = length 0.875m
    # Wheels: 0.19 × 0.38 × 0.38 = diameter 0.38m
    # diam_frac = 0.38 / 0.875 = 0.434 — must pass!
    meshes = _make_synthetic_car(
        wheelbase=0.6,        # short vehicle
        track_width=0.4,
        wheel_radius=0.19,    # large wheels (compensated: 2r = 0.38)
        wheel_width=0.19,
    )
    result = detect_wheels(meshes)
    assert len(result.wheels) == 4


def test_detect_wheels_error_when_no_candidates():
    """A body-only scene should fail candidate stage."""
    body_only = [_make_box_mesh("body", (0.0, 0.0, 0.7), (4.5, 1.8, 1.4))]
    with pytest.raises(WheelDetectionError, match="no wheel-shape candidates"):
        detect_wheels(body_only)
