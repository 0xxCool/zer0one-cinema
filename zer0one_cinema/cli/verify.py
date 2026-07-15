"""`zocinema verify` — v0.2 command.

Runs 6-gate CGVF check on a folder of finished frames. Exit codes drive
CI integration: 0 = all PASS, 1 = at least one WARN, 2 = at least one FAIL.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click

from ..verify import verify_frames
from ..verify.report import VerifyReport, VerifyStatus

_STATUS_EMOJI = {
    VerifyStatus.PASS: "PASS",
    VerifyStatus.WARN: "WARN",
    VerifyStatus.FAIL: "FAIL",
    VerifyStatus.SKIP: "SKIP",
}

_EXIT = {
    VerifyStatus.PASS: 0,
    VerifyStatus.WARN: 1,
    VerifyStatus.FAIL: 2,
    VerifyStatus.SKIP: 0,
}


def _report_to_json(report: VerifyReport) -> str:
    """Serialize with sorted keys for deterministic diffs."""
    payload = asdict(report)
    payload["overall"] = report.overall.value
    for frame in payload["frames"]:
        for gate in frame["gates"]:
            gate["status"] = str(gate["status"])
    return json.dumps(payload, sort_keys=True, indent=2)


def _report_to_markdown(report: VerifyReport) -> str:
    """Human-readable side-by-side of the JSON."""
    lines: list[str] = [
        f"# CGVF verify — {report.overall.value}",
        "",
        f"**Version:** {report.version}",
        f"**Frames:** {len(report.frames)}",
        f"**Overall:** {report.overall.value}",
        "",
        "## Per-gate PASS rate",
    ]
    for gate, rate in sorted(report.gate_pass_rate.items()):
        lines.append(f"- **{gate}**: {rate * 100:.1f}%")
    lines.append("")
    lines.append("## Frames (first 20)")
    for fr in list(report.frames)[:20]:
        lines.append(f"### {Path(fr.frame_path).name}")
        for g in fr.gates:
            lines.append(
                f"- **{g.name}** ({_STATUS_EMOJI[g.status]}): "
                f"{', '.join(f'{k}={v}' for k, v in g.metrics.items())}"
            )
        lines.append("")
    return "\n".join(lines)


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
    help="Optional golden-frame directory for SSIM/PSNR regression (v0.3+).",
)
@click.option(
    "--report",
    "report_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write JSON report to this path; Markdown side-by-side gets .md extension.",
)
def verify_command(
    frames_dir: str,
    gates: str | None,
    strict: bool,
    reference_dir: str | None,
    report_path: str | None,
) -> None:
    """Run 6-gate CGVF check on a folder of rendered frames."""
    gate_list = [g.strip() for g in gates.split(",")] if gates else None

    report = verify_frames(
        frames_dir=frames_dir,
        gates=gate_list,
        reference_dir=reference_dir,
        strict=strict,
    )

    total = len(report.frames)
    click.echo(
        f"CGVF: {total} frames  ·  overall={report.overall.value}"
        + ("  ·  strict on" if strict else "")
    )
    for gate, rate in sorted(report.gate_pass_rate.items()):
        click.echo(f"  {gate:<15} PASS-rate {rate * 100:.1f}%")

    if report_path:
        json_path = Path(report_path)
        json_path.write_text(_report_to_json(report))
        md_path = json_path.with_suffix(".md")
        md_path.write_text(_report_to_markdown(report))
        click.echo(f"report → {json_path}  +  {md_path}")

    sys.exit(_EXIT[report.overall])
