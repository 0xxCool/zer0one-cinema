"""bpy-side adapters — the only file that imports bpy/bpy_extras/mathutils.

All Blender interaction (rendering, transform reads/writes, NDC projection)
funnels through this module. Unit tests substitute a MockAdapter with the
same surface so the loop, frame_analyzer, and fix_rules are testable
without a real Blender interpreter.

Filled in during Phase P5.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .fix_rules import SceneState
from .frame_analyzer import BBoxNDC
from .report import SceneMutation


@dataclass(frozen=True)
class RenderOutcome:
    """Result of one EEVEE preview render."""

    frame_path: str
    frame_bgr: np.ndarray  # (H, W, 3) uint8, OpenCV convention
    render_seconds: float


class PreflightAdapter(Protocol):
    """The surface the preflight loop needs from Blender."""

    def render_eevee_preview(self, output_path: str) -> RenderOutcome: ...

    def snapshot_scene_state(self, camera_name: str) -> SceneState: ...

    def bbox_to_ndc(self, camera_name: str) -> BBoxNDC: ...

    def apply_mutation(self, mutation: SceneMutation, camera_name: str) -> None: ...


def make_blender_adapter(scene_ref: object, car_object_name: str) -> PreflightAdapter:
    """Construct the real Blender adapter.

    Filled in during Phase P5.
    """
    raise NotImplementedError("phase P5")
