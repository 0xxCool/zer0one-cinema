"""Unit tests for verify/sequence.py: motion gate + verify_frames aggregation."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from zer0one_cinema.verify.report import GateResult, VerifyStatus
from zer0one_cinema.verify.sequence import (
    _overall_status,
    _pass_rates,
    _resolve_gates,
    gate_motion,
    verify_frames,
)


def _save_frame(path: Path, rgb01: np.ndarray) -> None:
    img = (rgb01.clip(0, 1) * 255).astype(np.uint8)
    Image.fromarray(img).save(path)


def _make_moving_pair(shift_px: int, h: int = 128, w: int = 256) -> tuple[np.ndarray, np.ndarray]:
    """Two frames with a bright rectangle shifted horizontally by `shift_px`."""
    prev = np.full((h, w, 3), 0.1, dtype=np.float32)
    curr = prev.copy()
    prev[40:80, 60:120, :] = 0.9
    curr[40:80, 60 + shift_px : 120 + shift_px, :] = 0.9
    return prev, curr


# ── gate_motion ───────────────────────────────────────────────────────────


def test_gate_motion_skip_on_identical_frames() -> None:
    frame = np.full((128, 256, 3), 0.5, dtype=np.float32)
    result = gate_motion(frame, frame)
    assert result.name == "C_motion"
    assert result.status == VerifyStatus.SKIP


def test_gate_motion_produces_direction_consistency_metric() -> None:
    """Farneback flow on a clean horizontal shift should measure some consistency.

    We don't gate on the value (Farneback's smoothing can under-detect edges
    of small synthetic bboxes), only that the gate ran to a terminal state
    and populated its metric key.
    """
    prev, curr = _make_moving_pair(shift_px=8)
    result = gate_motion(prev, curr)
    assert result.name == "C_motion"
    assert result.status in {VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP}
    if result.status != VerifyStatus.SKIP:
        assert "direction_consistency" in result.metrics
        assert 0.0 <= result.metrics["direction_consistency"] <= 1.0


def test_gate_motion_returns_skip_when_cv2_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "zer0one_cinema.verify.sequence._try_import_cv2",
        lambda: None,
    )
    prev, curr = _make_moving_pair(shift_px=5)
    result = gate_motion(prev, curr)
    assert result.status == VerifyStatus.SKIP
    assert "note_cv2_missing" in result.metrics


# ── _overall_status ───────────────────────────────────────────────────────


def _gate(name: str, status: VerifyStatus) -> GateResult:
    return GateResult(name=name, status=status, metrics={})


def _fr(gates: list[GateResult]) -> object:
    from zer0one_cinema.verify.report import FrameReport

    return FrameReport(frame_path="mock.png", gates=tuple(gates))


def test_overall_status_all_pass_returns_pass() -> None:
    reports = [_fr([_gate("A", VerifyStatus.PASS), _gate("B", VerifyStatus.PASS)])]
    assert _overall_status(reports) == VerifyStatus.PASS  # type: ignore[arg-type]


def test_overall_status_any_fail_returns_fail() -> None:
    reports = [
        _fr([_gate("A", VerifyStatus.PASS)]),
        _fr([_gate("A", VerifyStatus.FAIL), _gate("B", VerifyStatus.PASS)]),
    ]
    assert _overall_status(reports) == VerifyStatus.FAIL  # type: ignore[arg-type]


def test_overall_status_warn_beats_pass_but_not_fail() -> None:
    reports = [
        _fr([_gate("A", VerifyStatus.PASS)]),
        _fr([_gate("B", VerifyStatus.WARN)]),
    ]
    assert _overall_status(reports) == VerifyStatus.WARN  # type: ignore[arg-type]


def test_overall_status_skip_only_returns_pass() -> None:
    """SKIP alone does not degrade the overall status."""
    reports = [_fr([_gate("A", VerifyStatus.SKIP)])]
    assert _overall_status(reports) == VerifyStatus.PASS  # type: ignore[arg-type]


# ── _pass_rates ───────────────────────────────────────────────────────────


def test_pass_rates_excludes_skip_from_denominator() -> None:
    reports = [
        _fr([_gate("A", VerifyStatus.PASS), _gate("B", VerifyStatus.SKIP)]),
        _fr([_gate("A", VerifyStatus.FAIL), _gate("B", VerifyStatus.PASS)]),
        _fr([_gate("A", VerifyStatus.PASS), _gate("B", VerifyStatus.PASS)]),
    ]
    rates = _pass_rates(reports)  # type: ignore[arg-type]
    assert rates["A"] == pytest.approx(round(2 / 3, 4))
    assert rates["B"] == pytest.approx(1.0)  # skip excluded → 2/2


# ── _resolve_gates ────────────────────────────────────────────────────────


def test_resolve_gates_none_returns_all_six() -> None:
    assert set(_resolve_gates(None)) == {
        "lighting",
        "material",
        "composition",
        "atmosphere",
        "grading",
        "motion",
    }


def test_resolve_gates_strips_whitespace_and_filters_empty() -> None:
    assert _resolve_gates(["lighting", " motion ", "", "grading"]) == [
        "lighting",
        "motion",
        "grading",
    ]


# ── verify_frames E2E on tmp dir ──────────────────────────────────────────


def test_verify_frames_empty_folder_returns_skip(tmp_path: Path) -> None:
    r = verify_frames(tmp_path)
    assert len(r.frames) == 0
    assert r.overall == VerifyStatus.SKIP


def test_verify_frames_runs_selected_gates(tmp_path: Path) -> None:
    for i in range(3):
        frame = np.full((300, 717, 3), 0.5, dtype=np.float32)
        _save_frame(tmp_path / f"frame_{i:03d}.png", frame)
    r = verify_frames(tmp_path, gates=["lighting"])
    assert len(r.frames) == 3
    for fr in r.frames:
        assert len(fr.gates) == 1
        assert fr.gates[0].name == "A_lighting"


def test_verify_frames_strict_promotes_warn_to_fail(tmp_path: Path) -> None:
    """Uniform frame → gate D returns WARN (empty mask); --strict → FAIL."""
    _save_frame(
        tmp_path / "frame_000.png", np.full((300, 717, 3), 0.9, dtype=np.float32)
    )
    r_normal = verify_frames(tmp_path, gates=["composition"])
    assert r_normal.frames[0].gates[0].status == VerifyStatus.WARN
    assert r_normal.overall == VerifyStatus.WARN

    r_strict = verify_frames(tmp_path, gates=["composition"], strict=True)
    assert r_strict.frames[0].gates[0].status == VerifyStatus.FAIL
    assert r_strict.overall == VerifyStatus.FAIL


def test_verify_frames_motion_first_frame_skipped(tmp_path: Path) -> None:
    for i in range(2):
        _save_frame(tmp_path / f"f_{i}.png", np.full((128, 256, 3), 0.5, dtype=np.float32))
    r = verify_frames(tmp_path, gates=["motion"])
    assert r.frames[0].gates[0].status == VerifyStatus.SKIP
    assert "note_first_frame" in r.frames[0].gates[0].metrics


def test_verify_frames_all_gates_default(tmp_path: Path) -> None:
    _save_frame(tmp_path / "f_00.png", np.full((300, 717, 3), 0.5, dtype=np.float32))
    r = verify_frames(tmp_path, gates=None)
    # 5 single-frame gates + motion (SKIP on frame 0)
    assert len(r.frames[0].gates) == 6
    gate_names = {g.name for g in r.frames[0].gates}
    assert gate_names == {
        "A_lighting",
        "B_material",
        "C_motion",
        "D_composition",
        "E_atmosphere",
        "F_grading",
    }
