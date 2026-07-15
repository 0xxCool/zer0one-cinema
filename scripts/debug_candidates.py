"""Debug script: dump per-mesh aspect-ratios so we can see WHY Stage 2 rejects.

Usage:
    blender -b -P scripts/debug_candidates.py -- <glb-path>
"""
from __future__ import annotations

import site
import sys
from pathlib import Path

site.ENABLE_USER_SITE = True
sys.path.insert(0, site.getusersitepackages())

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

user_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
if not user_args:
    print("usage: blender -b -P scripts/debug_candidates.py -- <glb-path>")
    sys.exit(2)
glb_path = user_args[0]

import numpy as np

from zer0one_cinema.io.bpy_adapters import wrap_mesh_objects
from zer0one_cinema.io.glb_loader import load_glb
from zer0one_cinema.model_prep.wheel_detect import (
    _project_to_frame,
    compute_vehicle_frame,
)

scene = load_glb(glb_path)
adapters = wrap_mesh_objects(list(scene.all_meshes))
all_verts = np.concatenate([np.asarray(a.world_verts, dtype=np.float64) for a in adapters])
frame = compute_vehicle_frame(all_verts)

# Vehicle scale
local_verts = _project_to_frame(all_verts, frame)
veh_len = float(local_verts[:, 0].max() - local_verts[:, 0].min())
veh_h = float(local_verts[:, 2].max() - local_verts[:, 2].min())
print(f"\n=== Vehicle scale: length={veh_len:.3f}m height={veh_h:.3f}m ===")
print(f"    forward-axis: {frame.forward_axis}")
print(f"    right-axis:   {frame.right_axis}")
print(f"    up-axis:      {frame.up_axis}")

# Thresholds
from zer0one_cinema.model_prep.wheel_detect import (
    _ASPECT_DISC_MAX,
    _ASPECT_DISC_MIN,
    _ASPECT_SHORT_MAX,
    _ASPECT_SHORT_MIN,
    _DIAM_FRAC_MAX,
    _DIAM_FRAC_MIN,
    _Y_FRAC_MAX,
)

print(
    f"\n=== Thresholds: aspect_short={_ASPECT_SHORT_MIN}-{_ASPECT_SHORT_MAX}, "
    f"aspect_disc={_ASPECT_DISC_MIN}-{_ASPECT_DISC_MAX}, "
    f"diam_frac={_DIAM_FRAC_MIN}-{_DIAM_FRAC_MAX}, "
    f"y_frac_max={_Y_FRAC_MAX} ==="
)

# Per-mesh dump
from zer0one_cinema.model_prep.bbox_utils import world_bbox_corners

print(f"\n=== {len(adapters)} meshes ===")
for a in adapters:
    corners = world_bbox_corners(a)
    corners_local = _project_to_frame(corners, frame)
    c_min = corners_local.min(axis=0)
    c_max = corners_local.max(axis=0)
    c_dims = c_max - c_min
    dims_sorted = np.sort(c_dims)
    short, mid, longd = float(dims_sorted[0]), float(dims_sorted[1]), float(dims_sorted[2])
    aspect_short = short / longd if longd > 0 else 0
    aspect_disc = mid / longd if longd > 0 else 0
    diam_frac = longd / veh_len if veh_len > 0 else 0
    c_center = (c_min + c_max) / 2.0
    veh_min_z = float(local_verts[:, 2].min())
    y_frac = (c_center[2] - veh_min_z) / veh_h if veh_h > 0 else 0.5

    passes = []
    passes.append("aspect_short=✓" if _ASPECT_SHORT_MIN <= aspect_short <= _ASPECT_SHORT_MAX else f"aspect_short=✗({aspect_short:.2f})")
    passes.append("aspect_disc=✓" if _ASPECT_DISC_MIN <= aspect_disc <= _ASPECT_DISC_MAX else f"aspect_disc=✗({aspect_disc:.2f})")
    passes.append("diam_frac=✓" if _DIAM_FRAC_MIN <= diam_frac <= _DIAM_FRAC_MAX else f"diam_frac=✗({diam_frac:.2f})")
    passes.append("y_frac=✓" if y_frac <= _Y_FRAC_MAX else f"y_frac=✗({y_frac:.2f})")

    print(
        f"  {a.name:<22} dims=({short:.2f}×{mid:.2f}×{longd:.2f})  "
        f"aspect_short={aspect_short:.2f} aspect_disc={aspect_disc:.2f} "
        f"diam_frac={diam_frac:.2f} y_frac={y_frac:.2f}  → {', '.join(passes)}"
    )
