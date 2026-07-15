"""RS6 Hero-Reveal Orbit v3 — cinema-grade lookdev fix.

v2 fixed the ground-anchor bug (tires now stand on ground). v3 fixes the
cinema-grade look:

* Neon-Cubes AS reflection-targets replaced by 2 vertical NEON tubes
  positioned BEHIND the car — they now reflect as clean vertical streaks
  in the paint instead of a diffuse cyan/pink wash.
* Wheels/rims get a dedicated dark metallic material (Metallic 0.9,
  Roughness 0.4, dark charcoal) — v2 left them as GLB default matte-white.
* Car body gets a real 3-layer car paint: metallic base + flake layer
  (Voronoi bump + roughness variation) + clearcoat, adapted from the
  blender-lookdev-carpaint skill.
* Exposure -0.35 to compensate for the emissive world/rims wash.
* Volume scatter density halved: 0.002 instead of 0.004 — v2's atmospheric
  haze was too thick, contributing to the "flat / washed out" impression.
* View transform AgX + AgX Punchy (unchanged, already correct).
* Ground-anchor logic from v2 (bpy.ops.transform.translate over all mesh
  verts) is preserved verbatim — that fix must not regress.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import bpy  # type: ignore[import-not-found]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument(
        "--glb",
        default=os.environ.get("ZOCINEMA_GLB", "/workspace/job/rs6.glb"),
    )
    p.add_argument(
        "--out-blend",
        default=os.environ.get(
            "ZOCINEMA_OUT_BLEND", "/workspace/job/output/rs6_hero_reveal_v3.blend"
        ),
    )
    p.add_argument(
        "--out-frames",
        default=os.environ.get("ZOCINEMA_OUT_FRAMES", "/workspace/job/output/frames"),
    )
    p.add_argument("--hdri", default=os.environ.get("ZOCINEMA_HDRI", ""))
    p.add_argument("--start", type=int, default=int(os.environ.get("ZOCINEMA_START", "1")))
    p.add_argument("--end", type=int, default=int(os.environ.get("ZOCINEMA_END", "192")))
    p.add_argument("--samples", type=int, default=int(os.environ.get("ZOCINEMA_SAMPLES", "64")))
    p.add_argument("--width", type=int, default=int(os.environ.get("ZOCINEMA_WIDTH", "1920")))
    p.add_argument("--height", type=int, default=int(os.environ.get("ZOCINEMA_HEIGHT", "1080")))
    p.add_argument("--build-only", action="store_true")
    return p.parse_args(argv)


def import_rs6_toolchain_anchored(glb_path: str) -> tuple[list, object]:
    """Import GLB, then use the real zer0one-cinema toolkit to ground-anchor.

    Returns (rs6_mesh_objects, car_collection). Bit-identical to v2 —
    do not touch, the ground fix depends on this exact sequence.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    new_objs = [o for o in bpy.data.objects if o not in before]
    rs6_meshes = [o for o in new_objs if o.type == "MESH"]

    def _compute_min_z() -> float:
        return min((m.matrix_world @ v.co).z for m in rs6_meshes for v in m.data.vertices)

    pre_min = _compute_min_z()
    print(f"    RS6 raw min_z (world, all verts): {pre_min:+.4f} m")

    bpy.ops.object.select_all(action="DESELECT")
    for m in rs6_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = rs6_meshes[0]
    dz = -pre_min
    bpy.ops.transform.translate(value=(0.0, 0.0, dz))
    bpy.context.view_layer.update()

    post_min = _compute_min_z()
    post_max = max((m.matrix_world @ v.co).z for m in rs6_meshes for v in m.data.vertices)
    print(f"    Post-shift RS6 z-range: [{post_min:+.4f}, {post_max:+.4f}]")
    print(f"    Shift applied: {dz:+.4f} m")

    if abs(post_min) > 0.002:
        print(f"    [!!] ABORT: min_z is {post_min:+.4f}m off from 0 — tires would sink/float!")
        sys.exit(3)
    print(f"    ✓ tires touch ground within ±2mm — safe to render")

    car_col = bpy.data.collections.new("car")
    bpy.context.scene.collection.children.link(car_col)
    for m in rs6_meshes:
        car_col.objects.link(m)
        for c in list(m.users_collection):
            if c is not car_col:
                c.objects.unlink(m)
    return rs6_meshes, car_col


def build_studio_set_v3(scene: object, hdri_path: str) -> None:
    """Cinema-grade studio: infinite wet-asphalt ground, dark world with
    volumetric haze, 2 vertical neon tubes BEHIND the car (clean streak
    reflections, not diffuse wash), 3-point key/rim/ambient rig."""
    bpy.ops.mesh.primitive_plane_add(size=10000, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    mat = bpy.data.materials.new("wet_asphalt_v3")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.010, 0.012, 0.016, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Metallic"].default_value = 0.0
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 1.0
    ground.data.materials.append(mat)

    world = bpy.data.worlds.new("hero_world_v3")
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
        bg.inputs["Strength"].default_value = 0.30
        print(f"    HDRI: {hdri_path}")
    else:
        bg.inputs["Color"].default_value = (0.003, 0.004, 0.007, 1.0)
        bg.inputs["Strength"].default_value = 1.0
        print("    HDRI: none — using near-black world")
    vol = nt.nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Density"].default_value = 0.002
    vol.inputs["Anisotropy"].default_value = 0.5
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    scene.world = world

    # ── 2 vertical NEON tubes BEHIND the car (magenta left, cyan right) ──
    # Height 4.5m, thin (0.15 x 3.0m), positioned OFF-axis so they produce
    # long clean reflection streaks in the paint instead of a diffuse wash.
    neon_specs = [
        # (x, y, z, rot_deg, color, energy, size_x, size_y, size_z)
        (-7.0, -6.0, 2.5, (0, 0, 30), (1.0, 0.08, 0.55), 40, 0.15, 3.0, 4.5),
        (7.0, -6.0, 2.5, (0, 0, -30), (0.08, 0.75, 1.0), 40, 0.15, 3.0, 4.5),
    ]
    for i, (x, y, z, rot, color, energy, sx, sy, sz) in enumerate(neon_specs):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
        n = bpy.context.object
        n.name = f"neon_v3_{i}"
        n.scale = (sx, sy, sz)
        n.rotation_euler = tuple(math.radians(v) for v in rot)
        m = bpy.data.materials.new(f"neon_v3_{i}_mat")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (*color, 1.0)
        b.inputs["Emission Strength"].default_value = energy
        # Kill diffuse — pure emitter
        b.inputs["Base Color"].default_value = (0, 0, 0, 1)
        b.inputs["Roughness"].default_value = 1.0
        n.data.materials.append(m)

    # ── 3-point rig: cool key + warm rim + soft ambient ──
    bpy.ops.object.light_add(type="AREA", location=(-6, 6, 8))
    key = bpy.context.object
    key.name = "KEY"
    key.data.energy = 1500
    key.data.size = 10
    key.data.color = (0.75, 0.85, 1.0)
    key.rotation_euler = (math.radians(55), 0, math.radians(-30))

    bpy.ops.object.light_add(type="AREA", location=(6, -5, 3.5))
    rim = bpy.context.object
    rim.name = "RIM"
    rim.data.energy = 900
    rim.data.size = 4
    rim.data.color = (1.0, 0.55, 0.30)
    rim.rotation_euler = (math.radians(70), 0, math.radians(160))

    bpy.ops.object.light_add(type="AREA", location=(0, 0, 14))
    amb = bpy.context.object
    amb.name = "AMB"
    amb.data.energy = 200
    amb.data.size = 20
    amb.data.color = (0.5, 0.65, 0.9)


def _get_bsdf(material):
    """Return the Principled BSDF node of a material, or None."""
    if not material or not material.use_nodes:
        return None
    return material.node_tree.nodes.get("Principled BSDF")


def _install_flake_layer(material, base_rough=0.32):
    """Add Voronoi-flake bump + roughness variation to a Principled BSDF material."""
    nt = material.node_tree
    bsdf = _get_bsdf(material)
    if bsdf is None:
        return
    # Voronoi with a huge scale = tiny flake cells
    voro = nt.nodes.new("ShaderNodeTexVoronoi")
    voro.location = (-500, -100)
    voro.inputs["Scale"].default_value = 2200.0

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-280, -100)
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[1].position = 0.62
    nt.links.new(voro.outputs["Distance"], ramp.inputs["Fac"])

    # Roughness modulation: flakes glitter (lower roughness at flake peaks)
    mixr = nt.nodes.new("ShaderNodeMix")
    mixr.location = (0, -160)
    mixr.data_type = "FLOAT"
    mixr.inputs["A"].default_value = base_rough
    mixr.inputs["B"].default_value = max(base_rough - 0.25, 0.05)
    nt.links.new(ramp.outputs["Color"], mixr.inputs["Factor"])
    nt.links.new(mixr.outputs["Result"], bsdf.inputs["Roughness"])

    # Subtle bump — sells the flakes in motion
    bump = nt.nodes.new("ShaderNodeBump")
    bump.location = (0, -360)
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(ramp.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def apply_rs6_materials_v3(rs6_meshes: list) -> None:
    """Assign materials by name pattern:

    * paint / body   → nardo-grey metallic 3-layer car paint
    * wheel / rim / felge → dark charcoal metal (not matte-white!)
    * tire / reifen  → matte black rubber
    * caliper / brake → matte deep-red

    Passes silently over anything else — GLB import materials for
    glass, chrome, plastic, etc. stay untouched.
    """
    paint_count = wheel_count = tire_count = caliper_count = 0
    for m in rs6_meshes:
        for slot in m.material_slots:
            mat = slot.material
            if not mat:
                continue
            name = mat.name.lower()
            b = _get_bsdf(mat)
            if b is None:
                mat.use_nodes = True
                b = _get_bsdf(mat)
                if b is None:
                    continue

            if any(k in name for k in ("paint", "body", "kit1_paint")):
                # Nardo Grey metallic
                b.inputs["Base Color"].default_value = (0.055, 0.062, 0.070, 1.0)
                b.inputs["Metallic"].default_value = 1.0
                b.inputs["Roughness"].default_value = 0.32
                if "Coat Weight" in b.inputs:
                    b.inputs["Coat Weight"].default_value = 1.0
                    b.inputs["Coat Roughness"].default_value = 0.02
                elif "Clearcoat" in b.inputs:
                    b.inputs["Clearcoat"].default_value = 1.0
                    b.inputs["Clearcoat Roughness"].default_value = 0.02
                _install_flake_layer(mat, base_rough=0.32)
                paint_count += 1
            elif any(k in name for k in ("wheel", "rim", "felge", "hub")):
                # Dark charcoal metal (turbine grey)
                b.inputs["Base Color"].default_value = (0.045, 0.048, 0.052, 1.0)
                b.inputs["Metallic"].default_value = 0.95
                b.inputs["Roughness"].default_value = 0.38
                if "Coat Weight" in b.inputs:
                    b.inputs["Coat Weight"].default_value = 0.5
                    b.inputs["Coat Roughness"].default_value = 0.15
                wheel_count += 1
            elif any(k in name for k in ("tire", "tyre", "reifen", "rubber")):
                # Matte deep-black rubber
                b.inputs["Base Color"].default_value = (0.014, 0.014, 0.014, 1.0)
                b.inputs["Metallic"].default_value = 0.0
                b.inputs["Roughness"].default_value = 0.75
                tire_count += 1
            elif any(k in name for k in ("caliper", "brake", "bremse")):
                # Signal-red brake calipers
                b.inputs["Base Color"].default_value = (0.42, 0.03, 0.03, 1.0)
                b.inputs["Metallic"].default_value = 0.3
                b.inputs["Roughness"].default_value = 0.35
                caliper_count += 1
    print(
        f"    Materials override: paint={paint_count} wheel={wheel_count} "
        f"tire={tire_count} caliper={caliper_count}"
    )


def setup_orbit_camera(scene: object, start: int, end: int) -> object:
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

    scene.frame_start = start
    scene.frame_end = end
    radius = 12.0
    z = 1.8
    for f in range(start, end + 1):
        angle = (f - start) / (end - start + 1) * 2 * math.pi
        cam.location = (radius * math.cos(angle), radius * math.sin(angle), z)
        cam.keyframe_insert(data_path="location", frame=f)
    if cam.animation_data and cam.animation_data.action:
        for fcurve in cam.animation_data.action.fcurves:
            for kp in fcurve.keyframe_points:
                kp.interpolation = "LINEAR"
    return cam


def configure_render(
    scene: object, width: int, height: int, samples: int, frames_dir: str
) -> None:
    scene.render.engine = "CYCLES"
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
    for cand in ("OPTIX", "OPENIMAGEDENOISE"):
        try:
            scene.cycles.denoiser = cand
            print(f"    Denoiser: {cand}")
            break
        except TypeError:
            continue
    else:
        scene.cycles.use_denoising = False
        print("    Denoiser: none available — off")
    scene.cycles.motion_blur = True
    scene.cycles.motion_blur_shutter = 0.5
    # AgX + Punchy — correct color pipeline
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    # Slight negative exposure to keep the neon tubes in the roll-off,
    # not clipped — punchier midtones, deeper blacks.
    scene.view_settings.exposure = -0.35
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "16"
    if frames_dir and not frames_dir.startswith("/workspace/") or os.access(
        os.path.dirname(frames_dir or "/tmp"), os.W_OK
    ):
        try:
            os.makedirs(frames_dir, exist_ok=True)
            scene.render.filepath = os.path.join(frames_dir, "frame_")
        except (OSError, PermissionError):
            print(f"    [WARN] frames-dir {frames_dir} not writable — set at render time")

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
    print(f">>> RS6 Hero-Reveal Orbit v3 ({args.start}–{args.end}), build-only={args.build_only}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    rs6_meshes, _car_col = import_rs6_toolchain_anchored(args.glb)
    build_studio_set_v3(scene, args.hdri)
    apply_rs6_materials_v3(rs6_meshes)
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
