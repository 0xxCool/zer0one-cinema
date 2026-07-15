"""`zocinema preflight` — v0.2 command.

Loads a `.blend` file (from `zocinema model-prep`), runs the preflight
render-analyze-fix loop with MAX_ITERS=3, and either passes (exit 0) or
aborts with a structured JSON report (exit 10/11/12/20).

Requires `bpy` + `opencv-contrib-python` + `scikit-image` — the command
emits clean errors when either is missing, pointing at the install hint.

Filled in during Phase P6.
"""
from __future__ import annotations

import click


@click.command("preflight")
@click.argument("blend_path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--camera",
    "-c",
    required=True,
    help="Name of the camera object inside the .blend to use.",
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
    type=click.Path(dir_okay=False),
    default=None,
    help="Write preflight report JSON to this path.",
)
@click.option("--seed", type=int, default=0, show_default=True, help="RNG seed.")
def preflight_command(
    blend_path: str,
    camera: str,
    max_iters: int,
    output_dir: str,
    report: str | None,
    seed: int,
) -> None:
    """Filled in during Phase P6."""
    raise click.UsageError("preflight command not implemented — arrives in phase P6")
