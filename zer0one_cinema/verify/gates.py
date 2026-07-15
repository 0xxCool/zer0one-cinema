"""The 6 CGVF gates: A_lighting, B_material, C_motion, D_composition,
E_atmosphere, F_grading.

Migrated + refactored from ~/zer0one-web/.claude/skills/cinema-grade-
verification/scripts/verify_frame.py. Retains the numpy+PIL-only surface
(no cv2 hard-dependency here — the OpenCV-specific gates live in
sequence.py).

Filled in during Phase P2.
"""
from __future__ import annotations

import numpy as np

from .report import GateResult


def gate_lighting(rgb: np.ndarray) -> GateResult:
    raise NotImplementedError("phase P2")


def gate_material(rgb: np.ndarray) -> GateResult:
    raise NotImplementedError("phase P2")


def gate_composition(rgb: np.ndarray) -> GateResult:
    raise NotImplementedError("phase P2")


def gate_atmosphere(rgb: np.ndarray) -> GateResult:
    raise NotImplementedError("phase P2")


def gate_grading(rgb: np.ndarray) -> GateResult:
    raise NotImplementedError("phase P2")


GATES = {
    "lighting": gate_lighting,
    "material": gate_material,
    "composition": gate_composition,
    "atmosphere": gate_atmosphere,
    "grading": gate_grading,
    # "motion" lives in sequence.py — needs 2 consecutive frames
}
