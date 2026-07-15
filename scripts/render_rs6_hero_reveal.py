"""RS6 Hero-Reveal Orbit — 192-frame cinema shot for zer0one-cinema dogfood.

The first real Cinema-Grade Render produced by v0.2.0. Camera orbits a
stationary RS6 for 360° over 8 s @ 24 fps, on a Studio-Set (inf. ground +
neon rim + HDRI sky). No path animation for the car — this structurally
excludes the RB4-RB8 fail-class (schwebt / Curve-falsch / Fahrtrichtung).

Usage:
    blender -b -P render_rs6_hero_reveal.py -- \
        --glb <rs6.glb> --out-blend <path> [--build-only] \
        [--start N --end M --out-frames <dir>] [--hdri <path>]

Modes:
    --build-only         : Only build the scene and save the .blend. No render.
                           Used before the preflight gate.
    (default)            : Build the scene AND render frames [--start..--end].
                           Used on RunPod for the full-render pass.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import bpy  # type: ignore[import-not-found]


def parse_args() -> argparse.Namespace:
    """Args pass through Blender's `--` separator; when invoked from
    `runpod_render.sh` the shell-expansion of `-- $SCRIPT_ARGS` may drop
    args, so every path defaults to the RunPod workspace convention
    (`/workspace/job/…`). Env vars (ZOCINEMA_*) override defaults for
    ad-hoc SSH invocation.
    """
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument(
        "--glb",
        default=os.environ.get("ZOCINEMA_GLB", "/workspace/job/rs6.glb"),
    )
    p.add_argument(
        "--out-blend",
        default=os.environ.get(
            "ZOCINEMA_OUT_BLEND", "/workspace/job/output/rs6_hero_reveal.blend"
        ),
    )
    p.add_argument(
        "--out-frames",
        default=os.environ.get("ZOCINEMA_OUT_FRAMES", "/workspace/job/output/frames"),
    )
    p.add_argument("--hdri", default=os.environ.get("ZOCINEMA_HDRI", ""))
    p.add_argument("--start", type=int, default=int(os.environ.get("ZOCINEMA_START", "1")))
    p.add_argument("--end", type=int, default=int(os.environ.get("ZOCINEMA_END", "192")))
    p.add_argument("--samples", type=int, default=int(os.environ.get("ZOCINEMA_SAMPLES", "128")))
    p.add_argument("--width", type=int, default=int(os.environ.get("ZOCINEMA_WIDTH", "1920")))
    p.add_argument("--height", type=int, default=int(os.environ.get("ZOCINEMA_HEIGHT", "1080")))
    p.add_argument("--build-only", action="store_true")
    return p.parse_args(argv)


def reset_scene() -> object:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def import_rs6_and_bundle_as_car_collection(glb_path: str) -> tuple[list[object], object]:
    """Import GLB, gather every mesh into a Collection named 'car', z-align
    so the lowest vertex sits at z=0.

    Returns (rs6_meshes, car_collection).
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    new_objs = [o for o in bpy.data.objects if o not in before]
    rs6_meshes = [o for o in new_objs if o.type == "MESH"]

    # ── Z-align (analog to model-prep's ground_anchor) ──
    sample = [m.matrix_world @ v.co for m in rs6_meshes[:20] for v in m.data.vertices[:200]]
    min_z = min(v.z for v in sample)
    top_level = [o for o in new_objs if o.parent is None or o.parent not in new_objs]
    for o in top_level:
        o.location.z -= min_z
    print(f"    RS6: {len(rs6_meshes)} meshes, z-shifted by {-min_z:+.3f}m")

    # ── Bundle into Collection 'car' so `zocinema preflight --car car` finds them ──
    car_col = bpy.data.collections.new("car")
    bpy.context.scene.collection.children.link(car_col)
    for m in rs6_meshes:
        car_col.objects.link(m)
        # Also unlink from previous scene collection so we only count once
        for c in list(m.users_collection):
            if c is not car_col:
                c.objects.unlink(m)
    return rs6_meshes, car_col


def build_studio_set(scene: object, hdri_path: str) -> None:
    """Infinite ground + HDRI sky + neon rim + 3-point key lights."""
    # ── Infinite wet-asphalt ground (analog cinema_hero_studio.py) ──
    bpy.ops.mesh.primitive_plane_add(size=10000, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("wet_asphalt")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.015, 0.018, 0.022, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.06
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.85
    ground.data.materials.append(mat)

    # ── World / HDRI ──
    world = bpy.data.worlds.new("hero_world")
    world.use_nodes = True
    nt = world.node_tree
    for n in nt.nodes:
        nt.nodes.remove(n)
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    if hdri_path and os.path.exists(hdri_path):
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdri_path)
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.35
        print(f"    HDRI: {hdri_path}")
    else:
        bg.inputs["Color"].default_value = (0.008, 0.010, 0.015, 1.0)
        bg.inputs["Strength"].default_value = 1.0
        print("    HDRI: none — using dark ambient")
    vol = nt.nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Density"].default_value = 0.004
    vol.inputs["Anisotropy"].default_value = 0.5
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    scene.world = world

    # ── Neon rim walls (defensive rectangle, orbit-safe) ──
    ring_r = 9.0
    neon_specs = [
        (ring_r, 0, 2.5, (0.1, 0.85, 1.0), 20),  # right — cyan
        (-ring_r, 0, 2.5, (1.0, 0.15, 0.7), 20),  # left — magenta
        (0, ring_r, 2.5, (0.2, 1.0, 0.6), 18),  # back — green-cyan
        (0, -ring_r, 2.5, (1.0, 0.9, 0.1), 18),  # front — warm yellow
    ]
    for i, (x, y, z, color, energy) in enumerate(neon_specs):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
        n = bpy.context.object
        n.name = f"neon_{i}"
        n.scale = (0.3, 3.0, 1.2)
        mat = bpy.data.materials.new(f"neon_{i}_mat")
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (*color, 1.0)
        b.inputs["Emission Strength"].default_value = energy
        n.data.materials.append(mat)

    # ── 3-point lighting ──
    bpy.ops.object.light_add(type="AREA", location=(-8, 5, 10))
    key = bpy.context.object
    key.name = "KEY"
    key.data.energy = 1000
    key.data.size = 12
    key.data.color = (0.65, 0.8, 1.0)
    key.rotation_euler = (math.radians(50), 0, math.radians(-30))

    bpy.ops.object.light_add(type="AREA", location=(5, 4, 2.5))
    rim = bpy.context.object
    rim.name = "RIM"
    rim.data.energy = 1400
    rim.data.size = 3
    rim.data.color = (0.1, 0.9, 1.0)
    rim.rotation_euler = (math.radians(75), 0, math.radians(150))

    bpy.ops.object.light_add(type="AREA", location=(0, 0, 15))
    amb = bpy.context.object
    amb.name = "AMB"
    amb.data.energy = 300
    amb.data.size = 20
    amb.data.color = (0.5, 0.7, 1.0)


def override_rs6_paint(rs6_meshes: list[object]) -> None:
    """Nardo-grey clear-coated paint on any body/paint material."""
    for m in rs6_meshes:
        for slot in m.material_slots:
            if slot.material and any(k in slot.material.name.lower() for k in ("paint", "body")):
                slot.material.use_nodes = True
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    b.inputs["Base Color"].default_value = (0.09, 0.10, 0.11, 1.0)
                    b.inputs["Metallic"].default_value = 0.65
                    b.inputs["Roughness"].default_value = 0.10
                    if "Coat Weight" in b.inputs:
                        b.inputs["Coat Weight"].default_value = 1.0
                        b.inputs["Coat Roughness"].default_value = 0.02


def setup_orbit_camera(scene: object, start: int, end: int) -> object:
    """85 mm, Bezier-Circle orbit, TRACK_TO focus_target at car center."""
    bpy.ops.object.empty_add(location=(0, 0, 0.9))
    focus = bpy.context.object
    focus.name = "focus_target"

    bpy.ops.object.camera_add(location=(12, 0, 1.8))
    cam = bpy.context.object
    cam.name = "Cam"
    cam.data.lens = 85.0
    cam.data.sensor_width = 36
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.8
    cam.data.dof.focus_object = focus
    track = cam.constraints.new("TRACK_TO")
    track.target = focus
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam

    # ── Keyframe location around origin — 360° over [start..end] ──
    scene.frame_start = start
    scene.frame_end = end
    radius = 12.0
    z = 1.8
    for f in range(start, end + 1):
        angle = (f - start) / (end - start + 1) * 2 * math.pi
        cam.location = (radius * math.cos(angle), radius * math.sin(angle), z)
        cam.keyframe_insert(data_path="location", frame=f)
    # Linear interpolation → constant angular speed
    if cam.animation_data and cam.animation_data.action:
        for fcurve in cam.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"
    return cam


def configure_render(
    scene: object, width: int, height: int, samples: int, frames_dir: str
) -> None:
    scene.render.engine = "CYCLES"
    # ── GPU + OPTIX (auto-fallback to CPU/OIDN when unavailable, e.g. local build-only) ──
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "OPTIX"
        prefs.get_devices()
        optix_devices = [d for d in prefs.devices if d.type == "OPTIX"]
        if optix_devices:
            scene.cycles.device = "GPU"
            for d in prefs.devices:
                d.use = d.type == "OPTIX"
            print(f"    Cycles device: OPTIX × {len(optix_devices)}")
        else:
            raise RuntimeError("no OPTIX device")
    except (TypeError, RuntimeError) as exc:
        scene.cycles.device = "CPU"
        print(f"    Cycles device: CPU (no OPTIX: {exc})")
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    # OPTIX denoiser needs OPTIX device; OIDN works on CPU-only.
    try:
        scene.cycles.denoiser = "OPTIX"
    except TypeError:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.motion_blur = True
    scene.cycles.motion_blur_shutter = 0.5
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    if frames_dir:
        os.makedirs(frames_dir, exist_ok=True)
        scene.render.filepath = os.path.join(frames_dir, "frame_")

    # Compositor: subtle glare + chromatic-aberration lens
    scene.use_nodes = True
    cnt = scene.node_tree
    for n in cnt.nodes:
        cnt.nodes.remove(n)
    rl = cnt.nodes.new("CompositorNodeRLayers")
    glare = cnt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "STREAKS"
    glare.threshold = 1.0
    glare.streaks = 4
    glare.mix = -0.85
    lens = cnt.nodes.new("CompositorNodeLensdist")
    lens.inputs["Dispersion"].default_value = 0.004
    comp = cnt.nodes.new("CompositorNodeComposite")
    cnt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    cnt.links.new(glare.outputs["Image"], lens.inputs["Image"])
    cnt.links.new(lens.outputs["Image"], comp.inputs["Image"])


def main() -> None:
    args = parse_args()
    print(f">>> RS6 Hero-Reveal Orbit ({args.start}–{args.end}), build-only={args.build_only}")

    scene = reset_scene()
    rs6_meshes, _car_col = import_rs6_and_bundle_as_car_collection(args.glb)
    build_studio_set(scene, args.hdri)
    override_rs6_paint(rs6_meshes)
    cam = setup_orbit_camera(scene, args.start, args.end)
    configure_render(scene, args.width, args.height, args.samples, args.out_frames)
    print(f"    camera '{cam.name}' orbits at r=12m; frames {args.start}–{args.end}")

    os.makedirs(os.path.dirname(args.out_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out_blend)
    print(f"    saved {args.out_blend}")

    if args.build_only:
        print("DONE (build-only mode)")
        return

    if not args.out_frames:
        print("ERROR: --out-frames required when rendering", file=sys.stderr)
        sys.exit(2)
    print(f">>> Rendering frames [{args.start}..{args.end}] → {args.out_frames}")
    for f in range(args.start, args.end + 1):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(args.out_frames, f"frame_{f:04d}")
        bpy.ops.render.render(write_still=True)
    print(f"DONE — {args.end - args.start + 1} frames rendered")


if __name__ == "__main__":
    main()
