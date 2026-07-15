"""I/O layer: adapters that connect model_prep to the Blender runtime.

Modules in this package are the ONLY ones that need `bpy` to be importable —
the rest of `zer0one_cinema` works against pure-python Protocols (MeshLike,
MaterialLike, MutableObject). This isolation keeps the core library
unit-testable without a Blender installation.

Modules:
    glb_loader   — imports GLB files via `bpy.ops.import_scene.gltf`
    bpy_adapters — wraps bpy.types.Object/Material as protocol-satisfying objects
"""

from .glb_loader import GlbImportError, SceneImportResult, load_glb

__all__ = ["GlbImportError", "SceneImportResult", "load_glb"]
