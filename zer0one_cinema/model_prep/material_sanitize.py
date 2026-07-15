"""Material sanitizer: normalize PBR materials to sane, cinema-grade values.

**Status: skeleton.** Full implementation planned for Sprint 19 Phase 2.

Design (from `docs/research/pbr-auto-fix-heuristics.md`):

    Sketchfab/TurboSquid GLBs typically arrive with chaotic PBR setups:
    Emission accidentally set on the body ("blown out" renders), Roughness
    stuck at 0.5, Metallic at 0 on chrome trim, Alpha slightly-less-than-1
    causing transparency-sort bugs. Materials need to be normalized to
    reasonable, cinema-grade values BEFORE rendering.

    Three-pass classification:
        Pass 1 — regex match on material name (12+ patterns, prio-sorted
                 from specific-to-generic, DACH-fokussiert).
        Pass 2 — texture-signal analysis (128×128 downsample of Base Color +
                 metallic map, per-channel averages).
        Pass 3 — fallback to `default_plastic` (Metallic 0, Roughness 0.4).
                 NEVER fall back to Body-Paint; unknown → plastic.

    Whitelist: only apply presets to recognized material classes. Unknown
    materials pass through untouched. A rollback log (`SANITIZER_REPORT.json`)
    records every change so users can `zocinema undo`.

    Blender 4.x API traps (all guarded):
        "Clearcoat"           → "Coat Weight"
        "Clearcoat Roughness" → "Coat Roughness"
        "Transmission"        → "Transmission Weight"
        "Emission"            → "Emission Color" + "Emission Strength"
    Always iterate via `node.type == "BSDF_PRINCIPLED"`, never look up by name.

    Five most-impactful auto-fixes (all v0.1):
        1. Emission-Kill on Body classes (fixes "blown out")
        2. Alpha-Clamp: alpha ∈ (0.95, 1.0) → 1.0 exact
        3. Car-Paint formula: Metallic 0, Roughness 0.38, Coat Weight 1.0
        4. Chrome / Rim: Metallic 1.0, Roughness 0.05
        5. Rubber / Tire: Metallic 0, Roughness 0.85
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

MaterialClass = Literal[
    "car_paint",
    "chrome_trim",
    "rim_alloy",
    "glass_clear",
    "headlight_lens",
    "taillight_red",
    "rubber_tire",
    "carbon_fiber",
    "plastic_interior",
    "brake_rotor",
    "leather_seat",
    "unknown",
]


@dataclass(frozen=True)
class SanitizerReport:
    """Rollback record for one material sanitization.

    Records the material's original state and the sanitizer's classification
    so users can revert with `zocinema undo`.
    """

    material_name: str
    classified_as: MaterialClass
    changes: dict[str, dict[str, float]]  # {"emission_strength": {"from": 1.5, "to": 0.0}, ...}


def sanitize_materials(materials: Iterable[object]) -> list[SanitizerReport]:
    """Normalize PBR values of a scene's materials to cinema-grade defaults.

    Args:
        materials: iterable of Blender Material objects (bpy.types.Material).

    Returns:
        List of per-material reports for audit / rollback.

    Raises:
        NotImplementedError: skeleton only.
    """
    raise NotImplementedError(
        "material_sanitize.sanitize_materials: implementation pending "
        "(Sprint 19 Phase 2, task S19-P2-material_sanitize). "
        "See docs/research/pbr-auto-fix-heuristics.md."
    )
