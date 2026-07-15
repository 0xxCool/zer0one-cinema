"""Debug wheel_detect Stages 2+4 — show candidate count + cluster centers.

Usage:
    blender -b -P scripts/debug_wheel_stages.py -- <glb-path>
"""
from __future__ import annotations

import site
import sys
from pathlib import Path

site.ENABLE_USER_SITE = True
sys.path.insert(0, site.getusersitepackages())
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

user_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
glb_path = user_args[0]

import numpy as np

from zer0one_cinema.io.bpy_adapters import wrap_mesh_objects
from zer0one_cinema.io.glb_loader import load_glb
from zer0one_cinema.model_prep.wheel_detect import (
    _sort_candidates_canonical,
    cluster_candidates,
    compute_vehicle_frame,
    find_candidates,
    validate_rectangle,
    validate_symmetry,
)

scene = load_glb(glb_path)
adapters = wrap_mesh_objects(list(scene.all_meshes))
all_verts = np.concatenate([np.asarray(a.world_verts, dtype=np.float64) for a in adapters])
frame = compute_vehicle_frame(all_verts)
print(f"\nvehicle frame center: {tuple(round(x, 3) for x in frame.center)}")
print(f"vehicle forward: {tuple(round(x, 3) for x in frame.forward_axis)}")

candidates = find_candidates(adapters, frame)
print(f"\n=== Stage 2: {len(candidates)} candidates ===")
for c in candidates[:20]:
    print(f"  {c.mesh.name[:50]:<52} center_local={tuple(round(x, 3) for x in c.center_local)}")

if len(candidates) < 4:
    print("Cannot cluster — need at least 4 candidates")
    sys.exit(0)

canonical = _sort_candidates_canonical(candidates)
labels = cluster_candidates(canonical, k=4, seed=0)

# Group candidates by cluster label, compute cluster center
clusters: dict[int, list] = {}
for lbl, c in zip(labels, canonical, strict=True):
    clusters.setdefault(lbl, []).append(c)

print(f"\n=== Stage 4: {len(clusters)} clusters ===")
centers = []
for i in sorted(clusters):
    cluster_center = np.mean([c.center_local for c in clusters[i]], axis=0)
    centers.append(cluster_center)
    print(f"  Cluster {i}: {len(clusters[i]):>2} candidates, center_local={tuple(round(float(x), 3) for x in cluster_center)}")

centers_arr = np.array(centers)

# Stage 5: rectangle validation
print("\n=== Stage 5: rectangle + symmetry ===")
xy = centers_arr[:, :2]
dists = []
for i in range(4):
    for j in range(i + 1, 4):
        d = float(np.linalg.norm(xy[i] - xy[j]))
        dists.append(d)
dists.sort()
print(f"  6 pairwise distances (sorted): {[round(d, 3) for d in dists]}")
print(f"  Rectangle test (tol_rel=0.10):")
for a, b, name in ((0, 1, "short-edge"), (2, 3, "long-edge"), (4, 5, "diagonal")):
    diff = abs(dists[a] - dists[b])
    rel = diff / dists[b] if dists[b] > 0 else 0
    print(f"    {name}: {dists[a]:.3f} vs {dists[b]:.3f} → diff {diff:.3f} ({rel:.1%}) {'✓' if rel < 0.10 else '✗ (>10%)'}")

print(f"\n  validate_rectangle(tol=0.10): {validate_rectangle(centers_arr, 0.10)}")
print(f"  validate_rectangle(tol=0.20): {validate_rectangle(centers_arr, 0.20)}")
print(f"  validate_symmetry(tol=0.10):  {validate_symmetry(centers_arr, 0.10)}")
print(f"  validate_symmetry(tol=0.20):  {validate_symmetry(centers_arr, 0.20)}")
