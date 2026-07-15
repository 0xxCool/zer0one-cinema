"""GLB loader — wraps `bpy.ops.import_scene.gltf` with hardening.

Guards against the three common failure modes we've seen in production:

1. **Missing file** — clear FileNotFoundError instead of Blender's cryptic
   RuntimeError.
2. **Draco decoder missing** — if the GLB uses Draco compression and
   `libextern_draco.so` is missing (a known issue on Blender ≤ 4.0.2 and on
   some Linux distro packages, see docs/research/blender-api-limits.md §C3),
   we raise a `GlbImportError` with a fix-recipe pointer.
3. **Silent skip** — Blender's importer can silently skip meshes when a
   material or texture is invalid. We snapshot `bpy.data.objects` before and
   after to detect what was actually created.

This module requires `bpy` to be importable — it will raise ImportError
at call-time (not module-import time) if bpy is unavailable, so the rest
of `zer0one_cinema` remains usable in pure-Python mode.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SceneImportResult:
    """Return of `load_glb()` — a snapshot of what was imported."""

    root_objects: tuple[Any, ...]  # top-level bpy Objects created by this import
    all_meshes: tuple[Any, ...]  # every mesh-type Object (Objects with .type == "MESH")
    materials: tuple[Any, ...]  # every new bpy Material
    vert_count: int  # total vertex count across all imported meshes
    import_seconds: float  # wall-clock duration


class GlbImportError(RuntimeError):
    """Raised when GLB import fails (file missing, Draco missing, bpy error)."""


def _require_bpy() -> Any:
    """Import bpy at call-time; raise a clear error if unavailable."""
    try:
        import bpy
    except ImportError as e:
        raise GlbImportError(
            "bpy is not available in this Python. Run this command via "
            "Blender's bundled Python (e.g. `blender -b -P script.py`) or "
            "install a matching bpy wheel."
        ) from e
    return bpy


def load_glb(glb_path: str | Path) -> SceneImportResult:
    """Import a GLB into the current Blender scene and return a snapshot.

    Args:
        glb_path: filesystem path to a .glb file.

    Returns:
        SceneImportResult with references to the newly-created objects,
        meshes, materials, plus vertex-count and duration.

    Raises:
        GlbImportError: on missing file, missing Draco decoder, or any
            Blender import failure.
    """
    path = Path(glb_path)
    if not path.exists():
        raise GlbImportError(f"GLB file not found: {path}")
    if not path.suffix.lower() == ".glb":
        raise GlbImportError(f"expected .glb file, got: {path.name}")

    bpy = _require_bpy()

    # Snapshot before
    before_objects = set(bpy.data.objects)
    before_meshes = set(bpy.data.meshes)
    before_materials = set(bpy.data.materials)

    started = time.monotonic()
    try:
        bpy.ops.import_scene.gltf(filepath=str(path))
    except RuntimeError as e:
        msg = str(e).lower()
        if "draco" in msg or "libextern_draco" in msg:
            raise GlbImportError(
                f"Draco decoder missing (bpy.ops.import_scene.gltf failed on '{path.name}'). "
                f"Fix: use the official Blender 4.2+ tarball from download.blender.org "
                f"and ensure libextern_draco.so is on the library path. "
                f"See docs/research/blender-api-limits.md §C3."
            ) from e
        raise GlbImportError(f"bpy.ops.import_scene.gltf failed on '{path.name}': {e}") from e

    duration = time.monotonic() - started

    # Snapshot after
    new_objects = tuple(sorted(set(bpy.data.objects) - before_objects, key=lambda o: o.name))
    new_meshes_data = set(bpy.data.meshes) - before_meshes  # noqa: F841 (kept for future use)
    new_materials = tuple(sorted(set(bpy.data.materials) - before_materials, key=lambda m: m.name))

    # Filter mesh-type Objects (glTF-importer creates armature/empty objects too)
    mesh_objects = tuple(o for o in new_objects if getattr(o, "type", None) == "MESH")

    # Root-level objects (no parent among the new set)
    new_obj_set = set(new_objects)
    root_objects = tuple(o for o in new_objects if o.parent is None or o.parent not in new_obj_set)

    # Vertex count across all mesh objects
    vert_count = sum(len(o.data.vertices) for o in mesh_objects if o.data is not None)

    return SceneImportResult(
        root_objects=root_objects,
        all_meshes=mesh_objects,
        materials=new_materials,
        vert_count=vert_count,
        import_seconds=duration,
    )
