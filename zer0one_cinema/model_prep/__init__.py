"""Model-prep: canonicalize any vehicle GLB into a rigged Blender scene.

The pipeline stages, in canonical order:

    1. glb_loader        (I/O — outside this package)
    2. bbox_utils        [IMPLEMENTED v0.1]
    3. ground_anchor     [IMPLEMENTED v0.1]
    4. body_group        [SKELETON — v0.1 impl pending]
    5. wheel_detect      [SKELETON — v0.1 impl pending]
    6. origin_fix        [SKELETON — v0.1 impl pending]
    7. rolling_axis      [SKELETON — v0.1 impl pending]
    8. caliper_filter    [SKELETON — v0.1 impl pending]
    9. material_sanitize [SKELETON — v0.1 impl pending]

All stages are deterministic: same input → bit-identical output.
Whitelist-based: known cases are corrected, unknown inputs pass through.
Every operation logs a `TraceEntry` for rollback and audit.
"""

from .bbox_utils import AABB, MeshLike, scene_world_aabb, world_bbox_corners
from .ground_anchor import GroundAnchorReport, apply_z_shift, compute_z_shift, ground_anchor

__all__ = [
    "AABB",
    "GroundAnchorReport",
    "MeshLike",
    "apply_z_shift",
    "compute_z_shift",
    "ground_anchor",
    "scene_world_aabb",
    "world_bbox_corners",
]
