"""Generate preflight test fixtures: 4 .blend files with intentional bugs.

Usage:
    blender -b -P scripts/build_preflight_fixtures.py -- <output-dir>

Produces (under <output-dir>/):
- cutoff.blend       : camera too close on the right, car partially off-frame
- ground_edge.blend  : ground plane too small, far edge visible below car
- center_locked.blend: car dead-centered, no rule-of-thirds
- unfixable.blend    : camera BEHIND the car (z_min < 0), no fix can recover

Each fixture has:
- A "car" cube (name "body_00", conforms to model-prep body-group convention)
- A "Ground" plane
- A named camera ("Cam") with intentional bad framing/scale
- A key light so EEVEE-Next has something to render

The bugs are pure geometry — no bpy-4.x-specific dependencies beyond
open_mainfile / save_as_mainfile / add primitive.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy  # type: ignore[import-not-found]


def _reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.data.scenes[0].render.engine = "BLENDER_EEVEE_NEXT"
    bpy.data.scenes[0].render.resolution_x = 1280
    bpy.data.scenes[0].render.resolution_y = 720


def _add_car(name: str = "body_00", size: float = 2.0) -> object:
    bpy.ops.mesh.primitive_cube_add(size=size, location=(0.0, 0.0, size / 2.0))
    car = bpy.context.active_object
    car.name = name
    # Colorful material for saliency signal
    mat = bpy.data.materials.new(name="body_paint")
    mat.diffuse_color = (0.8, 0.1, 0.1, 1.0)
    car.data.materials.append(mat)
    return car


def _add_ground(name: str = "Ground", scale: float = 30.0) -> object:
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.active_object
    ground.name = name
    ground.scale = (scale, scale, 1.0)
    mat = bpy.data.materials.new(name="ground_asphalt")
    mat.diffuse_color = (0.2, 0.2, 0.2, 1.0)
    ground.data.materials.append(mat)
    return ground


def _add_camera(location: tuple[float, float, float], rot_euler: tuple[float, float, float], name: str = "Cam") -> object:
    bpy.ops.object.camera_add(location=location, rotation=rot_euler)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = 50.0
    # Make this the scene's active render camera — Blender needs it for `render.render`.
    bpy.context.scene.camera = cam
    return cam


def _add_key_light() -> None:
    bpy.ops.object.light_add(type="SUN", location=(5.0, -5.0, 10.0))
    sun = bpy.context.active_object
    sun.data.energy = 3.0


def build_cutoff(out_path: Path) -> None:
    """Car partially cut off on the right — fixable via cam_lateral_shift."""
    _reset_scene()
    _add_car()
    _add_ground()
    # Camera positioned so the car sits in the right ~10% of the frame:
    # place cam slightly LEFT of car so car appears far-right.
    _add_camera(
        location=(-3.5, -5.0, 1.5),
        rot_euler=(math.radians(75), 0.0, math.radians(-25)),
    )
    _add_key_light()
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))


def build_ground_edge(out_path: Path) -> None:
    """Ground plane too small — its far edge visible below the car."""
    _reset_scene()
    _add_car()
    _add_ground(scale=2.5)  # far too small
    _add_camera(
        location=(0.0, -6.0, 1.8),
        rot_euler=(math.radians(72), 0.0, 0.0),
    )
    _add_key_light()
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))


def build_center_locked(out_path: Path) -> None:
    """Car dead-centered in frame — fails rule-of-thirds."""
    _reset_scene()
    _add_car()
    _add_ground()
    _add_camera(
        location=(0.0, -6.0, 1.5),
        rot_euler=(math.radians(75), 0.0, 0.0),
    )
    _add_key_light()
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))


def build_unfixable(out_path: Path) -> None:
    """Camera BEHIND the car — z-negative bbox corners, no fix recovers."""
    _reset_scene()
    _add_car()
    _add_ground()
    # Camera on the far side of the car, looking away
    _add_camera(
        location=(0.0, 5.0, 1.5),
        rot_euler=(math.radians(90), 0.0, math.radians(180)),
    )
    _add_key_light()
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))


def main() -> None:
    if "--" not in sys.argv:
        print("usage: blender -b -P build_preflight_fixtures.py -- <output-dir>")
        sys.exit(2)
    args = sys.argv[sys.argv.index("--") + 1 :]
    if len(args) != 1:
        print("expected exactly one arg: <output-dir>")
        sys.exit(2)
    out_dir = Path(args[0])
    out_dir.mkdir(parents=True, exist_ok=True)

    build_cutoff(out_dir / "cutoff.blend")
    print(f"wrote {out_dir / 'cutoff.blend'}")
    build_ground_edge(out_dir / "ground_edge.blend")
    print(f"wrote {out_dir / 'ground_edge.blend'}")
    build_center_locked(out_dir / "center_locked.blend")
    print(f"wrote {out_dir / 'center_locked.blend'}")
    build_unfixable(out_dir / "unfixable.blend")
    print(f"wrote {out_dir / 'unfixable.blend'}")


if __name__ == "__main__":
    main()
