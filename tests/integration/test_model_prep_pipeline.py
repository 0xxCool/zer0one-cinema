"""E2E integration test — pure Python, no Blender required.

Builds a synthetic vehicle scene (4 wheels + body + realistic materials),
runs the full model-prep pipeline over it, and asserts each stage did the
right thing. This is the v0.1 acceptance test for the library layer.

Real Blender-based E2E-tests (with actual GLB files from Sketchfab/Khronos)
land in v0.1.5 when the Docker+Blender container is wired up.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from tests.unit.test_material_sanitize import _make_bsdf_material
from zer0one_cinema.model_prep import (
    build_body_group,
    detect_wheels,
    ground_anchor,
    sanitize_materials,
    set_wheel_origins_to_center,
)

# ---------------------------------------------------------------------------
# Synthetic car — mesh with vertices (for origin_fix) + world_verts (for wheel_detect)
# ---------------------------------------------------------------------------


class _FullMesh:
    """A mesh that satisfies BOTH NamedMeshLike (world_verts, matrix_world,
    bound_box, name) AND MutableObject (location, data.vertices).

    Used by the integration test to run wheel_detect + origin_fix on the
    same object without needing two different mock classes.
    """

    def __init__(
        self,
        name: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
    ) -> None:
        self.name = name
        cx, cy, cz = center
        sx, sy, sz = size
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        # matrix_world with translation
        self.matrix_world: list[list[float]] = [
            [1.0, 0.0, 0.0, cx],
            [0.0, 1.0, 0.0, cy],
            [0.0, 0.0, 1.0, cz],
            [0.0, 0.0, 0.0, 1.0],
        ]
        # bound_box in local coords
        self.bound_box: list[list[float]] = [
            [-hx, -hy, -hz],
            [-hx, -hy, hz],
            [-hx, hy, hz],
            [-hx, hy, -hz],
            [hx, -hy, -hz],
            [hx, -hy, hz],
            [hx, hy, hz],
            [hx, hy, -hz],
        ]
        # World-space vertices (used by wheel_detect PCA)
        world_corners = []
        for local in self.bound_box:
            world_corners.append([local[0] + cx, local[1] + cy, local[2] + cz])
        self.world_verts = np.array(world_corners, dtype=np.float64)
        # Mutable location for origin_fix
        self.location: list[float] = [cx, cy, cz]
        # Mutable vertex list (start in local coords)
        self.data = _MeshData(vertices=[_Vertex(co=list(local)) for local in self.bound_box])


class _Vertex:
    def __init__(self, co: list[float]) -> None:
        self.co = co


class _MeshData:
    def __init__(self, vertices: list[_Vertex]) -> None:
        self.vertices = vertices


# ---------------------------------------------------------------------------
# Synthetic scene builder
# ---------------------------------------------------------------------------


def _make_synthetic_car() -> tuple[list[_FullMesh], list[Any]]:
    """Return (meshes, materials) for a full 4-wheel car.

    Wheels + body geometry laid out around world origin (X=forward, Y=right, Z=up).
    Realistic PBR materials with mock-BSDF nodes.
    """
    wheel_radius = 0.35
    wheel_width = 0.22
    wheelbase = 2.7
    track = 1.6
    wheel_z = wheel_radius

    meshes = [
        _FullMesh("body_paint", center=(0.0, 0.0, 0.7), size=(4.5, 1.8, 1.4)),
        _FullMesh(
            "wheel_FL",
            center=(+wheelbase / 2, -track / 2, wheel_z),
            size=(2 * wheel_radius, wheel_width, 2 * wheel_radius),
        ),
        _FullMesh(
            "wheel_FR",
            center=(+wheelbase / 2, +track / 2, wheel_z),
            size=(2 * wheel_radius, wheel_width, 2 * wheel_radius),
        ),
        _FullMesh(
            "wheel_RL",
            center=(-wheelbase / 2, -track / 2, wheel_z),
            size=(2 * wheel_radius, wheel_width, 2 * wheel_radius),
        ),
        _FullMesh(
            "wheel_RR",
            center=(-wheelbase / 2, +track / 2, wheel_z),
            size=(2 * wheel_radius, wheel_width, 2 * wheel_radius),
        ),
    ]

    materials = [
        _make_bsdf_material("body_paint", inputs={"Emission Strength": 1.5, "Alpha": 0.99}),
        _make_bsdf_material("windshield_glass"),
        _make_bsdf_material("chrome_bumper"),
        _make_bsdf_material("tire_rubber_FL"),
        _make_bsdf_material("unknown_random_part"),
    ]
    return meshes, materials


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------


def test_e2e_synthetic_car_full_pipeline() -> None:
    meshes, materials = _make_synthetic_car()

    # Stage 1: ground_anchor — shift so lowest point (wheel-bottom) is at z=0
    ga_report = ground_anchor(meshes, top_level_objects=[])
    # The wheels are already at z=wheel_radius, so bottom = 0 → no shift needed
    assert ga_report["idempotent"] is True

    # Stage 2: detect_wheels — should find all 4
    wheel_result = detect_wheels(meshes)
    assert len(wheel_result.wheels) == 4
    labels = {w.label for w in wheel_result.wheels}
    assert labels == {"FL", "FR", "RL", "RR"}
    assert wheel_result.confidence >= 0.8

    # Stage 3: origin_fix — every wheel-mesh should be reported (moved or skipped).
    # In our synthetic scene the wheel-meshes are already at their centers,
    # so idempotence kicks in (skipped=4, moved=0). Both counts sum to the
    # aggregated rotating-mesh count.
    origin_report = set_wheel_origins_to_center(wheel_result.wheels)
    total_processed = origin_report.origins_moved + origin_report.skipped_already_centered
    assert total_processed >= 4  # one per wheel

    # Stage 4: build body group — should get the body mesh, exclude wheels
    body = build_body_group(meshes, wheel_result.wheels)
    assert len(body.meshes) == 1
    assert body.meshes[0].name == "body_paint"

    # Stage 5: sanitize_materials — should classify body/glass/chrome/tire correctly
    reports = sanitize_materials(materials)
    by_name = {r.material_name: r for r in reports}
    assert by_name["body_paint"].classified_as == "paint_body"
    assert by_name["windshield_glass"].classified_as == "glass"
    assert by_name["chrome_bumper"].classified_as == "chrome"
    assert by_name["tire_rubber_FL"].classified_as == "tire_rubber"
    # unknown → default_plastic (whitelist principle)
    assert by_name["unknown_random_part"].classified_as == "default_plastic"

    # Hard-fix on body: Emission Strength was 1.5 → 0.0, Alpha 0.99 → 1.0
    body_changes = {c.reason for c in by_name["body_paint"].changes}
    assert "emission-kill" in body_changes


def test_e2e_pipeline_idempotent() -> None:
    """Running the whole pipeline twice yields no changes on the second run."""
    meshes, materials = _make_synthetic_car()
    # First run
    ground_anchor(meshes, top_level_objects=[])
    wheels_1 = detect_wheels(meshes)
    set_wheel_origins_to_center(wheels_1.wheels)
    sanitize_materials(materials)

    # Second run: should be idempotent
    ga_2 = ground_anchor(meshes, top_level_objects=[])
    wheels_2 = detect_wheels(meshes)
    origin_2 = set_wheel_origins_to_center(wheels_2.wheels)
    reports_2 = sanitize_materials(materials)

    assert ga_2["idempotent"] is True
    assert origin_2.origins_moved == 0
    # No material changes on second run
    total_changes = sum(len(r.changes) for r in reports_2)
    assert total_changes == 0


def test_e2e_deterministic() -> None:
    """Same input + same seed → identical wheel labels + centers across runs."""
    meshes1, _ = _make_synthetic_car()
    meshes2, _ = _make_synthetic_car()
    r1 = detect_wheels(meshes1, seed=0)
    r2 = detect_wheels(meshes2, seed=0)
    assert [w.label for w in r1.wheels] == [w.label for w in r2.wheels]
    for w1, w2 in zip(r1.wheels, r2.wheels, strict=True):
        assert w1.center == pytest.approx(w2.center)
        assert w1.radius == pytest.approx(w2.radius)


def test_e2e_body_group_excludes_env_mesh() -> None:
    """A sky-mesh in the scene → filtered out by body_group's env-filter.

    Detect wheels on the clean scene first (a sky mesh would dilate the
    vehicle-length estimate in Stage 2 and drop the wheel candidates
    under-threshold), then include the sky when building the body group.
    """
    meshes_no_sky, _materials = _make_synthetic_car()
    wheel_result = detect_wheels(meshes_no_sky)

    # Now add sky and build body group — env-filter should catch it
    sky = _FullMesh("sky_dome", center=(0.0, 0.0, 0.0), size=(500.0, 500.0, 500.0))
    meshes_with_sky = meshes_no_sky + [sky]
    body = build_body_group(meshes_with_sky, wheel_result.wheels)
    assert body.excluded_env_meshes == 1
    body_names = {m.name for m in body.meshes}
    assert "sky_dome" not in body_names
    assert "body_paint" in body_names
