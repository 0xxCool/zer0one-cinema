"""Wheel-detection: identify k wheel-groups in a vehicle GLB.

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design (from `docs/research/wheel-detection-methods.md`):

    Six-stage pipeline, deterministic throughout.

    1. candidate_extraction — collect sub-meshes with aspect-ratio consistent
       with a cylinder (short × mid × long ≈ 1 × 2 × 2, symmetric about the
       shortest local axis).
    2. axis_alignment — determine forward and side axes via a body-mesh PCA.
       glTF's own axis convention is unreliable (Sketchfab exports are
       notoriously inconsistent).
    3. clustering — K-Means (k=4 default; auto-detect for motorcycle/truck).
       Deterministic trick: sort candidate points lexicographically BEFORE
       calling `.fit()`, and use `n_init=1, random_state=0`. K-Means is only
       bit-reproducible when input order is fixed.
    4. radius_fit — verify each cluster forms a cylinder within a tolerance;
       reject singletons and outliers.
    5. symmetry_test — the 4 wheel centers must form a rectangle (wheelbase
       × track-width); reject if not.
    6. caliper_filter — for each wheel cluster, separate rotating parts
       (rim + tire; within 20% of wheel radius from axis) from static parts
       (caliper + brake disc; radial offset > 20%).

Edge cases (documented in research):
- Motorcycle (k=2): auto-detect on candidate count.
- Truck / lorry (k≥6): auto-detect via multi-axle rectangles.
- Spare wheel on trunk: 5th cylinder outside the two wheelbase clusters —
  reject before K-Means, else it drags the cluster.
- Brake disc inside wheel cluster: radial-distance test in stage 6.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .bbox_utils import MeshLike


@dataclass(frozen=True)
class WheelGroup:
    """One detected wheel: the sub-meshes that make it up, its center, and its rolling axis.

    Attributes:
        meshes: sub-meshes belonging to this wheel (rim, tire, hub-nuts, etc.).
        center: world-space center of rotation as (x, y, z).
        rolling_axis: which local axis the wheel rolls around ('x', 'y', or 'z').
        radius: wheel radius in metres (from bounding-box fit).
        static_meshes: caliper / brake-disc meshes that must NOT rotate with the wheel.
    """

    meshes: tuple[MeshLike, ...]
    center: tuple[float, float, float]
    rolling_axis: str
    radius: float
    static_meshes: tuple[MeshLike, ...] = ()


def detect_wheels(meshes: Iterable[MeshLike], k: int | None = None) -> list[WheelGroup]:
    """Detect wheel groups in a vehicle scene.

    Args:
        meshes: all sub-meshes of the vehicle (post ground-anchor).
        k: expected wheel count. If None, auto-detected from candidate count
            (4 for typical car, 2 for motorcycle, 6/8 for lorries).

    Returns:
        List of `WheelGroup` instances (typically length 4).

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "wheel_detect.detect_wheels: implementation pending (Sprint 19 Phase 2, "
        "task S19-P2-wheel_detect). See docs/research/wheel-detection-methods.md."
    )
