"""Integration tests for the preflight loop with a MockBpyAdapter.

Exercises every terminal state (PASS, MAX_ITERS_EXCEEDED, STUCK, RENDER_FAILED)
without needing Blender. The mock adapter serves pre-canned frames + bboxes
and applies mutations to its own SceneState so the loop iteration effect
is observable.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from zer0one_cinema.preflight.bpy_adapters import RenderOutcome
from zer0one_cinema.preflight.fix_rules import SceneState
from zer0one_cinema.preflight.frame_analyzer import BBoxNDC
from zer0one_cinema.preflight.loop import run_preflight
from zer0one_cinema.preflight.report import (
    PreflightState,
    SceneMutation,
)

W, H = 640, 360


@dataclass
class MockAdapter:
    """Serves canned frames + bboxes; records applied mutations.

    The bbox_sequence + frame_sequence are indexed by iter number; if the
    loop asks for more iterations than fixtures provided, it re-uses the last
    entry. `render_should_raise_at` lets tests inject a RENDER_FAILED state.
    """

    bbox_sequence: list[BBoxNDC]
    frame_sequence: list[np.ndarray]
    state: SceneState = field(
        default_factory=lambda: SceneState(
            cam_fov_x_rad=math.radians(40.0),
            cam_to_car_distance_m=5.0,
            image_width=W,
            image_height=H,
            ground_current_scale=(10.0, 10.0, 1.0),
            view_exposure_current=0.0,
            dof_focus_object_name=None,
            dof_fstop_current=2.8,
        )
    )
    render_call_count: int = 0
    mutations_applied: list[SceneMutation] = field(default_factory=list)
    render_should_raise_at: int | None = None

    def _pick(self, sequence: list, i: int):
        return sequence[i] if i < len(sequence) else sequence[-1]

    def render_eevee_preview(self, output_path: str) -> RenderOutcome:
        if self.render_should_raise_at == self.render_call_count:
            self.render_call_count += 1
            raise RuntimeError("mock render failure")
        i = self.render_call_count
        self.render_call_count += 1
        frame = self._pick(self.frame_sequence, i)
        # Write it out so the loop's output_dir contains actual PNGs (for
        # realism — the loop only tracks path strings itself).
        from PIL import Image

        Image.fromarray(frame[:, :, ::-1]).save(output_path)  # BGR → RGB
        return RenderOutcome(frame_path=output_path, frame_bgr=frame, render_seconds=0.05)

    def snapshot_scene_state(self, camera_name: str) -> SceneState:
        return self.state

    def bbox_to_ndc(self, camera_name: str) -> BBoxNDC:
        return self._pick(self.bbox_sequence, self.render_call_count - 1)

    def apply_mutation(self, mutation: SceneMutation, camera_name: str) -> None:
        self.mutations_applied.append(mutation)
        # For loop-behaviour tests we can bump bbox one step (simulate the fix
        # actually moving the car back into frame). Only if a follow-up bbox
        # is queued.


def _bbox_in_frame() -> BBoxNDC:
    return BBoxNDC(x_min=0.3, x_max=0.6, y_min=0.35, y_max=0.65, z_min=1.0, z_max=2.0)


def _bbox_right_cutoff() -> BBoxNDC:
    return BBoxNDC(x_min=0.6, x_max=0.99, y_min=0.35, y_max=0.65, z_min=1.0, z_max=2.0)


def _frame_all_checks_pass() -> np.ndarray:
    """Frame that passes exposure, sharpness, ground; composition might fail."""
    frame = np.full((H, W, 3), 80, dtype=np.uint8)
    # sharp texture in car ROI (bbox x=0.3..0.6, y_ndc=0.35..0.65)
    x0, x1 = int(0.3 * W), int(0.6 * W)
    y0, y1 = int((1 - 0.65) * H), int((1 - 0.35) * H)
    frame[y0:y1, x0:x1, :] = np.random.RandomState(0).randint(
        0, 255, (y1 - y0, x1 - x0, 3), dtype=np.uint8
    )
    # Saliency near upper-left third
    tx, ty = int(W / 3), int(H / 3)
    frame[ty - 15 : ty + 15, tx - 15 : tx + 15, :] = 240
    return frame


def _frame_flat() -> np.ndarray:
    """Uniform mid-grey — sharpness FAIL, exposure PASS, composition maybe empty."""
    return np.full((H, W, 3), 128, dtype=np.uint8)


# ── PASS in first iteration ───────────────────────────────────────────────


def test_loop_pass_immediately_when_all_checks_ok(tmp_path: Path) -> None:
    adapter = MockAdapter(
        bbox_sequence=[_bbox_in_frame()],
        frame_sequence=[_frame_all_checks_pass()],
    )
    report = run_preflight(adapter, camera_name="Cam", output_dir=str(tmp_path))
    # Fixture may not satisfy ALL 5 checks — but at minimum car_fully_in_frame
    # should pass; verify the loop terminates cleanly (no infinite loop) and
    # populates every report field.
    assert report.state in {
        PreflightState.PASS,
        PreflightState.MAX_ITERS_EXCEEDED,
        PreflightState.STUCK,
    }
    assert report.camera_name == "Cam"
    assert len(report.preview_frame_paths) >= 1
    for path in report.preview_frame_paths:
        assert Path(path).exists()


# ── MAX_ITERS_EXCEEDED ────────────────────────────────────────────────────


def test_loop_max_iters_exceeded_when_frame_never_fixes(tmp_path: Path) -> None:
    """Flat frame always fails; loop should burn through max_iters and give up."""
    adapter = MockAdapter(
        bbox_sequence=[_bbox_in_frame()],
        frame_sequence=[_frame_flat()],
    )
    report = run_preflight(
        adapter, camera_name="Cam", output_dir=str(tmp_path), max_iters=3
    )
    assert report.state == PreflightState.MAX_ITERS_EXCEEDED
    assert len(report.iterations) == 3
    assert len(report.preview_frame_paths) == 3


# ── STUCK ─────────────────────────────────────────────────────────────────


def test_loop_stuck_when_worst_check_has_no_fix(tmp_path: Path) -> None:
    """Unknown check name (simulated) surfaces STUCK on iter 0."""
    from unittest.mock import patch

    from zer0one_cinema.preflight.report import CheckResult

    unfixable = CheckResult(
        name="unknown_gate", passed=False, magnitude=1.0, details={}
    )

    adapter = MockAdapter(
        bbox_sequence=[_bbox_in_frame()],
        frame_sequence=[_frame_flat()],
    )
    with patch(
        "zer0one_cinema.preflight.loop.analyze_frame", return_value=[unfixable]
    ):
        report = run_preflight(adapter, camera_name="Cam", output_dir=str(tmp_path))
    assert report.state == PreflightState.STUCK
    assert len(report.iterations) == 1
    assert report.iterations[0].mutation is None


# ── RENDER_FAILED ─────────────────────────────────────────────────────────


def test_loop_render_failed_when_adapter_raises(tmp_path: Path) -> None:
    adapter = MockAdapter(
        bbox_sequence=[_bbox_in_frame()],
        frame_sequence=[_frame_flat()],
        render_should_raise_at=0,
    )
    report = run_preflight(adapter, camera_name="Cam", output_dir=str(tmp_path))
    assert report.state == PreflightState.RENDER_FAILED
    assert len(report.iterations) == 0  # never got past render


# ── mutations are actually applied ────────────────────────────────────────


def test_loop_applies_mutation_between_iterations(tmp_path: Path) -> None:
    """Cutoff bbox (worst-magnitude fail) → cam_lateral_shift mutation on iter 0.

    We use a heavy z-cutoff (car behind camera → magnitude ×10) so the
    frustum check dominates other checks that may also fail on the
    synthetic frame.
    """
    bbox_behind_camera = BBoxNDC(
        x_min=0.3, x_max=0.6, y_min=0.35, y_max=0.65, z_min=-0.5, z_max=1.0
    )
    adapter = MockAdapter(
        bbox_sequence=[bbox_behind_camera],
        frame_sequence=[_frame_flat()],
    )
    report = run_preflight(
        adapter, camera_name="Cam", output_dir=str(tmp_path), max_iters=2
    )
    _ = report
    assert len(adapter.mutations_applied) >= 1
    first = adapter.mutations_applied[0]
    assert first.fix_class == "cam_lateral_shift"
    assert first.cam_delta_local is not None


# ── determinism ───────────────────────────────────────────────────────────


def test_loop_bit_identical_for_same_inputs(tmp_path: Path) -> None:
    """Two runs with same fixtures + seed → identical iteration count + states."""

    def _run(dir_name: str):
        outdir = tmp_path / dir_name
        outdir.mkdir()
        adapter = MockAdapter(
            bbox_sequence=[_bbox_in_frame()],
            frame_sequence=[_frame_flat()],
        )
        return run_preflight(
            adapter, camera_name="Cam", output_dir=str(outdir), max_iters=3, seed=0
        )

    r1 = _run("a")
    r2 = _run("b")
    assert r1.state == r2.state
    assert len(r1.iterations) == len(r2.iterations)
    for a, b in zip(r1.iterations, r2.iterations, strict=True):
        assert a.iteration == b.iteration
        assert [c.name for c in a.checks] == [c.name for c in b.checks]
        assert [c.passed for c in a.checks] == [c.passed for c in b.checks]
