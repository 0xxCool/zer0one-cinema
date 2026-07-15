"""`zocinema model-prep` — the v0.1 flagship command.

Runs the full model-preparation pipeline on a vehicle GLB:

    1. Load GLB (bpy.ops.import_scene.gltf)
    2. Ground-anchor: shift so lowest point is on z=0
    3. Detect wheels (K-Means k=4, deterministic)
    4. Set wheel origins to their geometric centers (so they spin, not fly off)
    5. Build body-group (non-wheel, non-env meshes)
    6. Sanitize materials (12-class PBR classifier + hard fixes)
    7. Save .blend + optional JSON report

Requires `bpy` at runtime — the command emits a clean error if bpy isn't
importable, pointing the user at `blender -b -P` as the recommended invocation.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from .. import __version__
from ..model_prep import (
    build_body_group,
    detect_wheels,
    ground_anchor,
    sanitize_materials,
    set_wheel_origins_to_center,
)


def _run_pipeline(
    glb_path: str,
    output_blend: str,
    seed: int,
    report_path: str | None,
) -> dict[str, Any]:
    """Run the full model-prep pipeline. Returns a summary dict."""
    # Deferred imports — these require bpy to be importable
    from ..io.bpy_adapters import wrap_mesh_objects
    from ..io.glb_loader import load_glb

    started = time.monotonic()

    # 1. Load GLB
    click.echo(f"[1/7] Loading {Path(glb_path).name}...")
    scene_result = load_glb(glb_path)
    click.echo(
        f"      → {len(scene_result.all_meshes)} meshes, "
        f"{scene_result.vert_count} vertices, "
        f"{scene_result.import_seconds:.2f}s"
    )

    # 2. Wrap bpy objects as protocol-satisfying adapters
    adapters = wrap_mesh_objects(list(scene_result.all_meshes))

    # 3. Ground anchor
    click.echo("[2/7] Ground-anchoring...")
    ga = ground_anchor(adapters, scene_result.root_objects)
    click.echo(f"      → z_shift = {ga['z_shift']:.4f} m, moved {ga['objects_moved']} objects")

    # 4. Detect wheels
    click.echo("[3/7] Detecting wheels...")
    # After ground_anchor, re-wrap so world_verts reflect new positions.
    # (bpy Objects mutate in place, so the adapters are still valid.)
    wheel_result = detect_wheels(adapters, seed=seed)
    click.echo(
        f"      → {len(wheel_result.wheels)} wheels: "
        f"{', '.join(w.label for w in wheel_result.wheels)} "
        f"(confidence {wheel_result.confidence:.2f})"
    )

    # 5. Set wheel origins to center
    click.echo("[4/7] Re-origining wheels...")
    origin_report = set_wheel_origins_to_center(wheel_result.wheels)
    click.echo(
        f"      → moved {origin_report.origins_moved} origins, "
        f"skipped {origin_report.skipped_already_centered} already-centered"
    )

    # 6. Build body group
    click.echo("[5/7] Building body group...")
    body = build_body_group(adapters, wheel_result.wheels)
    click.echo(
        f"      → {len(body.meshes)} body meshes "
        f"(excluded {body.excluded_wheel_meshes} wheel + {body.excluded_env_meshes} env)"
    )

    # 7. Sanitize materials
    click.echo("[6/7] Sanitizing materials...")
    material_reports = sanitize_materials(scene_result.materials)
    changed = sum(1 for r in material_reports if r.changes)
    click.echo(f"      → {len(material_reports)} materials analyzed, {changed} changed")

    # 8. Save .blend
    click.echo(f"[7/7] Saving {output_blend}...")
    import bpy

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(output_blend).absolute()))

    duration = time.monotonic() - started
    click.secho(f"✓ Done in {duration:.1f}s", fg="green")

    summary = {
        "version": __version__,
        "seed": seed,
        "input": glb_path,
        "output": output_blend,
        "duration_seconds": duration,
        "import": {
            "meshes": len(scene_result.all_meshes),
            "materials": len(scene_result.materials),
            "vertices": scene_result.vert_count,
            "seconds": scene_result.import_seconds,
        },
        "ground_anchor": ga,
        "wheels": {
            "count": len(wheel_result.wheels),
            "confidence": wheel_result.confidence,
            "labels": [w.label for w in wheel_result.wheels],
        },
        "origin_fix": {
            "moved": origin_report.origins_moved,
            "skipped": origin_report.skipped_already_centered,
        },
        "body_group": {
            "mesh_count": len(body.meshes),
            "centroid": body.centroid,
            "excluded_wheel_meshes": body.excluded_wheel_meshes,
            "excluded_env_meshes": body.excluded_env_meshes,
        },
        "materials": {
            "total": len(material_reports),
            "changed": changed,
            "per_material": [asdict(r) for r in material_reports],
        },
    }

    if report_path:
        Path(report_path).write_text(json.dumps(summary, indent=2, default=str))
        click.echo(f"  Report: {report_path}")

    return summary


@click.command()
@click.argument("glb_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(dir_okay=False, writable=True),
    help="Path to save the prepared .blend file.",
)
@click.option("--seed", type=int, default=0, show_default=True, help="RNG seed for K-Means.")
@click.option(
    "--report",
    "report_path",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Optional path to write a JSON report of everything the pipeline did.",
)
def model_prep_command(
    glb_path: str,
    output: str,
    seed: int,
    report_path: str | None,
) -> None:
    """Prepare a vehicle GLB for rendering: rig wheels, anchor ground, sanitize materials.

    The output .blend file is deterministic — identical GLB + identical seed
    produce byte-identical output. Requires Blender's Python (bpy) to be
    importable; recommended invocation:

        blender -b -P -c 'from zer0one_cinema.cli.main import main; main()' -- \\
            model-prep car.glb --output car_prepped.blend --report report.json
    """
    try:
        _run_pipeline(
            glb_path=glb_path,
            output_blend=output,
            seed=seed,
            report_path=report_path,
        )
    except Exception as e:
        click.secho(f"✗ Pipeline failed: {e}", fg="red", err=True)
        raise click.ClickException(str(e)) from e
