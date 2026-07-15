"""Adapters that let `bpy` types satisfy our protocol interfaces.

The model_prep layer works against Protocols (MeshLike, NamedMeshLike,
MaterialLike) — these are structurally satisfied by bpy types, but a few
attributes need small computed wrappers (chiefly `world_verts`, which is
not a bpy field but an expensive `matrix_world @ vertex.co` iteration).

None of these adapters allocate — they wrap bpy objects lazily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class BpyMeshAdapter:
    """Wraps a `bpy.types.Object` (mesh-type) as a NamedMeshLike.

    Exposes matrix_world / bound_box / name directly, and computes
    `world_verts` on demand via matrix_world × vertex.co.
    """

    obj: Any  # bpy.types.Object

    @property
    def name(self) -> str:
        return str(self.obj.name)

    @property
    def matrix_world(self) -> list[list[float]]:
        # Blender's Matrix is row-first indexable; convert to nested list.
        return [list(row) for row in self.obj.matrix_world]

    @property
    def bound_box(self) -> list[list[float]]:
        # bpy.bound_box is a sequence of 8 float3 (local-space corners)
        return [list(v) for v in self.obj.bound_box]

    @property
    def world_verts(self) -> np.ndarray:
        """All vertices in world space as (N, 3) float64 array.

        Warning: O(N) per call — cache the result if used multiple times.
        For meshes > 10k verts, consider sampling in the caller.
        """
        matrix_np = np.asarray(self.matrix_world, dtype=np.float64)
        local_verts = np.array(
            [[float(v.co[0]), float(v.co[1]), float(v.co[2]), 1.0] for v in self.obj.data.vertices],
            dtype=np.float64,
        )
        if local_verts.size == 0:
            return np.zeros((0, 3), dtype=np.float64)
        world = (matrix_np @ local_verts.T).T
        return world[:, :3]


def wrap_mesh_objects(bpy_objects: list[Any]) -> list[BpyMeshAdapter]:
    """Wrap a list of bpy mesh-type Objects as BpyMeshAdapter."""
    return [BpyMeshAdapter(obj=o) for o in bpy_objects if getattr(o, "type", None) == "MESH"]
