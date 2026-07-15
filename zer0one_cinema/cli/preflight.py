"""`zocinema preflight` — v0.2 command.

Loads a `.blend` file (typically from `zocinema model-prep`), runs the
preflight render-analyze-fix loop with MAX_ITERS=3, and either passes
(exit 0) or aborts with a structured JSON report (exit 10/11/12/20).

Requires `bpy` at runtime — the command is only callable via
`blender -b -P scripts/run_zocinema.py -- preflight …`.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from ..preflight.report import PreflightReport, PreflightState

_EXIT_CODES = {
    PreflightState.PASS: 0,
    PreflightState.MAX_ITERS_EXCEEDED: 10,
    PreflightState.STUCK: 11,
    PreflightState.RENDER_FAILED: 12,
    PreflightState.NO_CAR_FOUND: 20,
}


def _report_to_json(report: PreflightReport) -> str:
    """Serialize with sorted keys for deterministic diffs."""
    payload = asdict(report)
    payload["state"] = report.state.value
    return json.dumps(payload, sort_keys=True, indent=2)


def _report_to_markdown(report: PreflightReport) -> str:
    lines = [
        f"# Preflight — {report.state.value}",
        "",
        f"**Version:** {report.version}  ·  **Seed:** {report.seed}  ·  **Camera:** {report.camera_name}",
        f"**Iterations:** {len(report.iterations)}",
        f"**Preview frames:** {len(report.preview_frame_paths)}",
        "",
    ]
    for it in report.iterations:
        lines.append(f"## Iter {it.iteration}")
        for c in it.checks:
            emoji = "PASS" if c.passed else "FAIL"
            lines.append(
                f"- {emoji} **{c.name}** magnitude={c.magnitude:.4f}"
            )
        if it.mutation is not None:
            lines.append(f"  → fix: `{it.mutation.fix_class}`")
        lines.append("")
    return "\n".join(lines)


def _run_loop(
    blend_path: str,
    camera: str,
    car_object_name: str,
    ground_object_name: str,
    max_iters: int,
    output_dir: str,
    seed: int,
) -> PreflightReport:
    """Blender-side entry — imports bpy and drives the loop."""
    import bpy

    from .. import __version__
    from ..preflight.bpy_adapters import make_blender_adapter
    from ..preflight.loop import run_preflight
    from ..preflight.report import (
        PreflightReport as _PreflightReport,
    )
    from ..preflight.report import (
        PreflightState as _PreflightState,
    )

    bpy.ops.wm.open_mainfile(filepath=blend_path)

    if bpy.data.objects.get(camera) is None:
        return _PreflightReport(
            state=_PreflightState.NO_CAR_FOUND,
            version=__version__,
            seed=seed,
            camera_name=camera,
            iterations=(),
            preview_frame_paths=(),
        )

    adapter = make_blender_adapter(
        car_object_name=car_object_name,
        ground_object_name=ground_object_name,
    )
    return run_preflight(
        adapter=adapter,
        camera_name=camera,
        output_dir=output_dir,
        max_iters=max_iters,
        seed=seed,
    )


@click.command("preflight")
@click.argument("blend_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--camera",
    "-c",
    required=True,
    help="Name of the camera object inside the .blend to use.",
)
@click.option(
    "--car",
    "car_object_name",
    default="car",
    show_default=True,
    help="Name of the car Blender-collection OR object; falls back to meshes named 'body*'.",
)
@click.option(
    "--ground",
    "ground_object_name",
    default="Ground",
    show_default=True,
    help="Name of the ground plane object.",
)
@click.option(
    "--max-iters",
    type=int,
    default=3,
    show_default=True,
    help="Maximum render-analyze-fix iterations before giving up.",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False),
    default="preflight-frames",
    show_default=True,
    help="Where to write the per-iteration preview PNGs.",
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write preflight report JSON to this path (Markdown gets .md).",
)
@click.option("--seed", type=int, default=0, show_default=True, help="RNG seed.")
def preflight_command(
    blend_path: str,
    camera: str,
    car_object_name: str,
    ground_object_name: str,
    max_iters: int,
    output_dir: str,
    report_path: str | None,
    seed: int,
) -> None:
    """Analyze a preview frame + auto-fix known bug classes, before a full render."""
    try:
        report = _run_loop(
            blend_path=blend_path,
            camera=camera,
            car_object_name=car_object_name,
            ground_object_name=ground_object_name,
            max_iters=max_iters,
            output_dir=output_dir,
            seed=seed,
        )
    except ImportError as exc:
        raise click.UsageError(
            "preflight requires Blender: invoke via "
            "`blender -b -P scripts/run_zocinema.py -- preflight <blend> ...`"
        ) from exc

    click.echo(f"Preflight: {report.state.value}  ·  iterations={len(report.iterations)}")
    for it in report.iterations:
        fails = [c.name for c in it.checks if not c.passed]
        fix = it.mutation.fix_class if it.mutation is not None else "<no fix>"
        click.echo(f"  iter {it.iteration}: fails=[{', '.join(fails)}] → {fix}")

    if report_path:
        json_path = Path(report_path)
        json_path.write_text(_report_to_json(report))
        md_path = json_path.with_suffix(".md")
        md_path.write_text(_report_to_markdown(report))
        click.echo(f"report → {json_path}  +  {md_path}")

    sys.exit(_EXIT_CODES[report.state])
