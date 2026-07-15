"""Preflight state-machine loop.

Iterates render → analyze → pick-worst-fail → apply-fix, up to MAX_ITERS
times. Terminates with one of PreflightState values. Emits a full
PreflightReport for every terminal state (PASS or failure).

MAX_ITERS=3 is empirically justified — Restore-Assess-Repeat literature
(arXiv 2603.26385, 2507.05598) shows iteration 4+ typically brings
diminishing returns or regression.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .. import __version__
from .bpy_adapters import PreflightAdapter
from .fix_rules import compute_fix
from .frame_analyzer import PreflightContext, analyze_frame
from .report import (
    CheckResult,
    IterationLog,
    PreflightReport,
    PreflightState,
    SceneMutation,
)

MAX_ITERS_DEFAULT = 3


def run_preflight(
    adapter: PreflightAdapter,
    camera_name: str,
    output_dir: str,
    max_iters: int = MAX_ITERS_DEFAULT,
    seed: int = 0,
) -> PreflightReport:
    """Run the render-analyze-fix loop and return a terminal PreflightReport.

    Never raises for a preflight-domain failure (STUCK / MAX_ITERS / RENDER_FAILED
    / NO_CAR_FOUND) — every terminal state is encoded in the returned report.
    The CLI translates the state into an exit code.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    np.random.seed(seed)
    try:
        import cv2

        cv2.setRNGSeed(seed)
    except ImportError:
        pass

    iterations: list[IterationLog] = []
    preview_paths: list[str] = []

    for i in range(max_iters):
        preview_out = str(output_path / f"iter_{i:02d}.png")
        try:
            outcome = adapter.render_eevee_preview(preview_out)
        except Exception as exc:  # noqa: BLE001 - user-facing preflight domain, want to log any render fault
            return _build_report(
                state=PreflightState.RENDER_FAILED,
                iterations=iterations,
                preview_paths=preview_paths,
                camera_name=camera_name,
                seed=seed,
                extra_note=f"render failed at iter {i}: {type(exc).__name__}: {exc}",
            )
        preview_paths.append(outcome.frame_path)

        state = adapter.snapshot_scene_state(camera_name)
        bbox = adapter.bbox_to_ndc(camera_name)
        ctx = PreflightContext(
            bbox_ndc=bbox,
            image_width=state.image_width,
            image_height=state.image_height,
        )
        checks = analyze_frame(outcome.frame_bgr, ctx)

        if all(c.passed for c in checks):
            iterations.append(IterationLog(iteration=i, checks=tuple(checks), mutation=None))
            return _build_report(
                state=PreflightState.PASS,
                iterations=iterations,
                preview_paths=preview_paths,
                camera_name=camera_name,
                seed=seed,
            )

        worst = _pick_worst_fail(checks)
        mutation = compute_fix(worst, state)
        iterations.append(
            IterationLog(iteration=i, checks=tuple(checks), mutation=mutation)
        )
        if mutation is None:
            return _build_report(
                state=PreflightState.STUCK,
                iterations=iterations,
                preview_paths=preview_paths,
                camera_name=camera_name,
                seed=seed,
            )
        adapter.apply_mutation(mutation, camera_name)

    return _build_report(
        state=PreflightState.MAX_ITERS_EXCEEDED,
        iterations=iterations,
        preview_paths=preview_paths,
        camera_name=camera_name,
        seed=seed,
    )


def _pick_worst_fail(checks: list[CheckResult]) -> CheckResult:
    """Return the failing check with the largest magnitude.

    Ties are broken by checks[i] order (first defined wins) — deterministic.
    """
    fails = [c for c in checks if not c.passed]
    return max(fails, key=lambda c: c.magnitude)


def _build_report(
    state: PreflightState,
    iterations: list[IterationLog],
    preview_paths: list[str],
    camera_name: str,
    seed: int,
    extra_note: str | None = None,
) -> PreflightReport:
    _ = extra_note  # v0.3: propagate into report as an extra field
    return PreflightReport(
        state=state,
        version=__version__,
        seed=seed,
        camera_name=camera_name,
        iterations=tuple(iterations),
        preview_frame_paths=tuple(preview_paths),
    )


__all__ = ["MAX_ITERS_DEFAULT", "run_preflight", "SceneMutation"]
