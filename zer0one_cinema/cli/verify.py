"""`zocinema verify` — v0.2 command.

Runs 6-gate CGVF check on a folder of finished frames. Exit codes drive
CI integration: 0 = all PASS, 1 = at least one WARN, 2 = at least one FAIL.

Filled in during Phase P3.
"""
from __future__ import annotations

import click


@click.command("verify")
@click.argument("frames_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--gates",
    default=None,
    help="Comma-separated subset of gates to run (default: all 6).",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat WARN as FAIL — abort on any regression.",
)
@click.option(
    "--ref",
    "reference_dir",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Optional golden-frame directory for SSIM/PSNR regression.",
)
@click.option(
    "--report",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write verify report JSON to this path (Markdown side-by-side).",
)
def verify_command(
    frames_dir: str,
    gates: str | None,
    strict: bool,
    reference_dir: str | None,
    report: str | None,
) -> None:
    """Filled in during Phase P3."""
    raise click.UsageError("verify command not implemented — arrives in phase P3")
