"""Body-group: identify the vehicle body (non-wheel) as a single logical group.

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design:

    After `wheel_detect` identifies the 4 (or 2/6/8) wheels, every remaining
    mesh in the scene is *by default* body. We wrap those into a logical
    group with a parent Empty at the body's geometric centroid — this Empty
    then becomes the anchor for body-roll animation (in cornering) and body-
    pitch (in braking / acceleration).

    A minority of GLBs have "environment" meshes that were exported
    accidentally (ground plane, sky sphere, backdrop). These have bboxes
    much larger than the vehicle or centered far from the vehicle centroid;
    the filter is: any mesh whose bbox diagonal is > 3× vehicle diagonal,
    OR whose center is > 2× vehicle diagonal away, is env — skip.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .bbox_utils import MeshLike
from .wheel_detect import WheelGroup


@dataclass(frozen=True)
class BodyGroup:
    """The vehicle's body: all non-wheel, non-environment meshes as one group."""

    meshes: tuple[MeshLike, ...]
    centroid: tuple[float, float, float]  # world-space center-of-bbox


def build_body_group(all_meshes: Iterable[MeshLike], wheels: Iterable[WheelGroup]) -> BodyGroup:
    """Compute the body group from all meshes minus wheels minus environment.

    Args:
        all_meshes: every mesh in the imported scene.
        wheels: wheel-groups from `detect_wheels()`.

    Returns:
        A BodyGroup with all body meshes and their combined centroid.

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "body_group.build_body_group: implementation pending "
        "(Sprint 19 Phase 2, task S19-P2-body_group)."
    )
