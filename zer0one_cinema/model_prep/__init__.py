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
from .body_group import BodyGroup, BodyGroupError, build_body_group
from .caliper_filter import filter_all_static, filter_static_from_wheel
from .ground_anchor import GroundAnchorReport, apply_z_shift, compute_z_shift, ground_anchor
from .material_sanitize import (
    ChangeRecord,
    MaterialClass,
    MaterialLike,
    SanitizerReport,
    TextureSampler,
    apply_preset,
    classify_by_name,
    classify_by_texture,
    sanitize_materials,
)
from .origin_fix import (
    MutableObject,
    OriginChangeRecord,
    OriginFixReport,
    set_origin_to_center,
    set_wheel_origins_to_center,
)
from .rolling_axis import infer_rolling_axis
from .wheel_detect import (
    NamedMeshLike,
    VehicleFrame,
    WheelCandidate,
    WheelDetectionError,
    WheelDetectionResult,
    WheelGroup,
    aggregate_wheel_meshes,
    cluster_candidates,
    compute_vehicle_frame,
    detect_wheels,
    find_candidates,
    label_wheels_flfr_rlrr,
    validate_rectangle,
    validate_symmetry,
)

__all__ = [
    "AABB",
    "BodyGroup",
    "BodyGroupError",
    "ChangeRecord",
    "GroundAnchorReport",
    "MaterialClass",
    "MaterialLike",
    "MeshLike",
    "MutableObject",
    "NamedMeshLike",
    "OriginChangeRecord",
    "OriginFixReport",
    "SanitizerReport",
    "TextureSampler",
    "VehicleFrame",
    "WheelCandidate",
    "WheelDetectionError",
    "WheelDetectionResult",
    "WheelGroup",
    "aggregate_wheel_meshes",
    "apply_preset",
    "apply_z_shift",
    "build_body_group",
    "classify_by_name",
    "classify_by_texture",
    "cluster_candidates",
    "compute_vehicle_frame",
    "compute_z_shift",
    "detect_wheels",
    "filter_all_static",
    "filter_static_from_wheel",
    "find_candidates",
    "ground_anchor",
    "infer_rolling_axis",
    "label_wheels_flfr_rlrr",
    "sanitize_materials",
    "scene_world_aabb",
    "set_origin_to_center",
    "set_wheel_origins_to_center",
    "validate_rectangle",
    "validate_symmetry",
    "world_bbox_corners",
]
