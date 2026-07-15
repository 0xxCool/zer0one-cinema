"""Body-group: identify the vehicle body (non-wheel) as a single logical group.

After `wheel_detect` has identified the wheels, every remaining mesh in the
scene is *by default* body — the carrosserie, windows, grille, lights,
mirrors, interior. This module wraps those meshes into a `BodyGroup` with
a centroid (needed later for body-roll / body-pitch animation anchor).

Two filters exclude non-body meshes:

    1. **Wheel-meshes** — anything in `wheel.meshes` or `wheel.static_meshes`
       (rims, tires, hub-nuts, calipers, brake-disc-brackets).
    2. **Environment-meshes** — meshes that are clearly *not* part of the
       vehicle: a ground plane, a sky sphere, a backdrop, or a stray import
       artifact. Heuristic (both must hold to classify as env):
       - bbox-diagonal > 3× vehicle-bbox-diagonal, OR
       - bbox-center is > 2× vehicle-diagonal away from the vehicle center.

The centroid is the mean of the body-meshes' bbox-centers, not the
volumetric center — it's used as an animation-rig anchor point, and the
bbox-mean is stable across mesh-count variations.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from .bbox_utils import AABB, MeshLike, scene_world_aabb, world_bbox_corners
from .wheel_detect import WheelGroup

# ==========================================================================
# Data structure
# ==========================================================================


@dataclass(frozen=True)
class BodyGroup:
    """The vehicle's body: non-wheel, non-environment meshes as one group.

    Attributes:
        meshes: body meshes (typically 5–200 for a well-detailed car).
        centroid: geometric mean of body-mesh bbox-centers in world coords.
        bbox: tight world-space AABB enclosing all body meshes.
        excluded_wheel_meshes: how many meshes were filtered as wheel parts.
        excluded_env_meshes: how many meshes were filtered as environment.
    """

    meshes: tuple[MeshLike, ...]
    centroid: tuple[float, float, float]
    bbox: AABB
    excluded_wheel_meshes: int = 0
    excluded_env_meshes: int = 0


class BodyGroupError(ValueError):
    """Raised when body-group cannot be built (e.g. no non-wheel meshes)."""


# ==========================================================================
# Environment-mesh detection
# ==========================================================================


# A mesh is classified as "environment" if its bbox-diagonal exceeds
# `_ENV_DIAG_MULT` × the vehicle-bbox-diagonal, OR if its bbox-center is
# more than `_ENV_DISTANCE_MULT` × vehicle-diagonal away from the vehicle
# center. Values from the roadmap; tunable if false-positives appear.
_ENV_DIAG_MULT = 3.0
_ENV_DISTANCE_MULT = 2.0


def _bbox_diagonal(bbox: AABB) -> float:
    """Return the 3D diagonal length of an AABB."""
    dx = bbox.max_x - bbox.min_x
    dy = bbox.max_y - bbox.min_y
    dz = bbox.max_z - bbox.min_z
    return float(np.sqrt(dx * dx + dy * dy + dz * dz))


def _mesh_bbox_center_and_diagonal(mesh: MeshLike) -> tuple[np.ndarray, float]:
    """Compute a single mesh's world-space bbox-center and diagonal."""
    corners = world_bbox_corners(mesh)
    c_min = corners.min(axis=0)
    c_max = corners.max(axis=0)
    diag = float(np.linalg.norm(c_max - c_min))
    center = (c_min + c_max) / 2.0
    return center, diag


def _is_environment_mesh(
    mesh: MeshLike,
    vehicle_center: tuple[float, float, float],
    vehicle_diagonal: float,
) -> bool:
    """Return True if the mesh looks like an environment mesh (ground, sky, backdrop)."""
    center, diag = _mesh_bbox_center_and_diagonal(mesh)
    # Rule 1: mesh is enormous relative to the vehicle
    if diag > _ENV_DIAG_MULT * vehicle_diagonal:
        return True
    # Rule 2: mesh is far away from the vehicle center
    distance = float(np.linalg.norm(center - np.array(vehicle_center)))
    return bool(distance > _ENV_DISTANCE_MULT * vehicle_diagonal)


# ==========================================================================
# Top-level: build_body_group
# ==========================================================================


def build_body_group(
    all_meshes: Iterable[MeshLike],
    wheels: Iterable[WheelGroup],
) -> BodyGroup:
    """Compute the body-group from all meshes minus wheel-parts minus environment.

    Steps:
        1. Collect every mesh identity that belongs to any wheel (rotating +
           static). This is done by `id()` so that Protocol-only mocks work
           without requiring hashability.
        2. Compute the vehicle-scale reference from `scene_world_aabb` over
           the union of body-candidate + wheel meshes (approximation of the
           vehicle envelope for the env-filter).
        3. Filter: mesh is NOT a wheel-part AND NOT an env-mesh.
        4. Return `BodyGroup` with meshes + centroid + bbox + counters.

    Raises:
        BodyGroupError: if no meshes remain after filtering.
    """
    # 1. Wheel-mesh identity set
    wheel_ids: set[int] = set()
    for wheel in wheels:
        for m in wheel.meshes:
            wheel_ids.add(id(m))
        for m in wheel.static_meshes:
            wheel_ids.add(id(m))

    all_mesh_list = list(all_meshes)
    if not all_mesh_list:
        raise BodyGroupError("no meshes given")

    # 2. Vehicle-scale reference. Estimated from the wheelbase (max distance
    # between wheel centers) — a robust car-scale reference. Multiplied by
    # a safety factor so a typical body-mesh (diagonal ≈ 1.3–1.7× wheelbase)
    # is NOT itself classified as env. Falls back to disabling the env-filter
    # if we have fewer than 2 wheels (nothing reliable to compare against).
    wheels_list = list(wheels)
    wheel_meshes_all: list[MeshLike] = []
    for w in wheels_list:
        wheel_meshes_all.extend(w.meshes)
        wheel_meshes_all.extend(w.static_meshes)

    if len(wheels_list) >= 2:
        wheel_centers = np.array([w.center for w in wheels_list], dtype=np.float64)
        # Max pairwise wheel-center distance = wheelbase-diagonal (or track-width for k=2)
        max_pairwise = 0.0
        for i in range(len(wheel_centers)):
            for j in range(i + 1, len(wheel_centers)):
                d = float(np.linalg.norm(wheel_centers[i] - wheel_centers[j]))
                max_pairwise = max(max_pairwise, d)
        # Typical vehicle-diagonal ≈ 1.5× wheelbase-diagonal → env threshold at 3×
        vehicle_diag = max_pairwise * 1.5
        vehicle_center = tuple(wheel_centers.mean(axis=0).tolist())
        env_filter_active = True
    else:
        # No wheelbase reference — accept all non-wheel meshes without env-filter
        vehicle_aabb = scene_world_aabb(all_mesh_list)
        vehicle_center = vehicle_aabb.center
        vehicle_diag = _bbox_diagonal(vehicle_aabb)
        env_filter_active = False

    # 3. Filter
    body_meshes: list[MeshLike] = []
    excluded_wheels = 0
    excluded_env = 0
    for mesh in all_mesh_list:
        if id(mesh) in wheel_ids:
            excluded_wheels += 1
            continue
        if env_filter_active and _is_environment_mesh(mesh, vehicle_center, vehicle_diag):
            excluded_env += 1
            continue
        body_meshes.append(mesh)

    if not body_meshes:
        raise BodyGroupError(
            f"no body meshes found after filtering "
            f"(excluded {excluded_wheels} wheel + {excluded_env} env)"
        )

    # 4. Centroid + bbox
    centers_and_diags = [_mesh_bbox_center_and_diagonal(m) for m in body_meshes]
    centers = np.array([c for c, _ in centers_and_diags], dtype=np.float64)
    centroid_arr = centers.mean(axis=0)
    body_bbox = scene_world_aabb(body_meshes)

    return BodyGroup(
        meshes=tuple(body_meshes),
        centroid=(float(centroid_arr[0]), float(centroid_arr[1]), float(centroid_arr[2])),
        bbox=body_bbox,
        excluded_wheel_meshes=excluded_wheels,
        excluded_env_meshes=excluded_env,
    )
