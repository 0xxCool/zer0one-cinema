"""Material sanitizer: normalize PBR materials to sane cinema-grade values.

Implementation of `docs/research/pbr-auto-fix-heuristics.md`. Three-pass
classifier (regex → texture → default_plastic), then per-class PBR preset,
then hard-fixes (Emission-Kill, Alpha-Clamp, Blend-Mode-Consistency).

**Design principles:**
- Whitelist: unknown materials fall back to `default_plastic`, never to
  `paint_body` (accidental Coat + Metallic on random parts kills the look).
- Idempotent: re-running produces an empty change-set (same input state → no
  new changes recorded).
- Blender 4.x native: uses `Coat Weight` / `Emission Color` / `Emission
  Strength` / `Transmission Weight` socket names. Blender ≤ 3.6 (`Clearcoat`,
  `Emission`, `Transmission`) is explicitly NOT supported.
- Deterministic: materials are processed in name-sorted order.
- Testable without bpy: everything works against `MaterialLike` protocol.

**Not in v0.1 (deferred):**
- Normal-map Y-flip detection & auto-invert (needs image sampling)
- Sheen layer for leather_seat (nice-to-have)
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import numpy as np

# ==========================================================================
# Type definitions
# ==========================================================================


MaterialClass = Literal[
    "paint_body",
    "chrome",
    "chrome_trim",
    "rim_alloy",
    "glass",
    "headlight_lens",
    "taillight_red",
    "tire_rubber",
    "brake_rotor",
    "carbon_fiber",
    "interior_plastic",
    "leather_seat",
    "default_plastic",
]

ClassificationSource = Literal["name", "texture", "default"]

BlendMethod = Literal["OPAQUE", "BLEND", "CLIP", "HASHED"]

# ==========================================================================
# Protocols — testable without bpy
# ==========================================================================


class SocketLike(Protocol):
    """Minimal interface satisfied by `bpy.types.NodeSocket`."""

    default_value: Any
    is_linked: bool


class NodeLike(Protocol):
    """Minimal interface for a Principled BSDF node."""

    type: str  # e.g. "BSDF_PRINCIPLED"
    inputs: Any  # dict-like: name → SocketLike


class LinkLike(Protocol):
    from_node: NodeLike
    to_node: NodeLike
    to_socket: SocketLike


class NodeTreeLike(Protocol):
    nodes: Any  # iterable of NodeLike
    links: Any  # supports .remove(link)


class MaterialLike(Protocol):
    """Minimal interface satisfied by `bpy.types.Material`."""

    name: str
    use_nodes: bool
    blend_method: str  # writable — will be set to "OPAQUE" or "BLEND"
    node_tree: NodeTreeLike | None


class TextureSampler(Protocol):
    """Read a texture connected to a BSDF input, at a given resolution.

    Returns:
        numpy array of shape (H, W, 4) with float32 values in [0, 1],
        or None if the input is not connected to an image texture.
    """

    def sample(self, material: MaterialLike, input_name: str, size: int) -> np.ndarray | None: ...


# ==========================================================================
# Data structures
# ==========================================================================


@dataclass(frozen=True)
class ChangeRecord:
    """Record of one PBR-socket value change (for rollback)."""

    input_name: str  # BSDF socket name (e.g. "Roughness", "Coat Weight")
    old: Any  # previous value (float, tuple, or "linked")
    new: Any  # new value
    reason: str  # short human-readable why (e.g. "preset", "emission-kill")


@dataclass(frozen=True)
class SanitizerReport:
    """Complete report of one material's sanitization."""

    material_name: str
    classified_as: MaterialClass
    source: ClassificationSource
    changes: tuple[ChangeRecord, ...] = ()
    skipped_reason: str | None = None  # e.g. "no BSDF node", "use_nodes=False"


# ==========================================================================
# Constants — patterns, presets, socket names
# ==========================================================================


# Name-pattern classifier. Priority-sorted from specific → generic.
# Lowest priority number wins on conflict. DACH (DE + EN) coverage.
#
# Boundary strategy: `(?<![a-zA-Z])word(?![a-zA-Z])` — alpha-only word-boundary
# so underscore, hyphen, dot, digit, and whitespace all count as separators.
# Python's `\b` treats underscore as a word character (\b won't match at `_`),
# which breaks the common `part_type` naming convention in GLB exports.
def _alpha_bounded(alternatives: str) -> str:
    return rf"(?<![a-zA-Z])({alternatives})(?![a-zA-Z])"


_PATTERNS: tuple[tuple[int, MaterialClass, re.Pattern[str]], ...] = (
    (
        10,
        "glass",
        re.compile(_alpha_bounded(r"glass|window|windshield|scheibe|glas|fenster"), re.IGNORECASE),
    ),
    (20, "chrome", re.compile(_alpha_bounded(r"chrome|chrom|verchromt"), re.IGNORECASE)),
    (
        30,
        "tire_rubber",
        re.compile(_alpha_bounded(r"tire|tyre|rubber|reifen|gummi"), re.IGNORECASE),
    ),
    (40, "brake_rotor", re.compile(_alpha_bounded(r"brake|rotor|bremse"), re.IGNORECASE)),
    (50, "carbon_fiber", re.compile(_alpha_bounded(r"carbon|cf|karbon|kohlefaser"), re.IGNORECASE)),
    (60, "rim_alloy", re.compile(_alpha_bounded(r"rim|wheel|alloy|felge"), re.IGNORECASE)),
    (
        70,
        "headlight_lens",
        re.compile(_alpha_bounded(r"headlight|scheinwerfer|lens|lamp"), re.IGNORECASE),
    ),
    (
        80,
        "taillight_red",
        re.compile(_alpha_bounded(r"taillight|rueckleuchte|rücklicht"), re.IGNORECASE),
    ),
    (
        90,
        "paint_body",
        re.compile(
            _alpha_bounded(r"body|paint|lack|karosserie|hood|door|fender|bumper"),
            re.IGNORECASE,
        ),
    ),
    (
        100,
        "interior_plastic",
        re.compile(_alpha_bounded(r"dash|dashboard|interior|innen|console"), re.IGNORECASE),
    ),
    (
        110,
        "leather_seat",
        re.compile(_alpha_bounded(r"seat|leather|leder|sitz|ledersitz|ledersessel"), re.IGNORECASE),
    ),
    (120, "chrome_trim", re.compile(_alpha_bounded(r"trim|molding|zierleiste"), re.IGNORECASE)),
)


# PBR preset values per material class. Values ONLY apply if the corresponding
# BSDF socket is not linked to a texture (guarded in apply_preset()).
_PRESETS: dict[MaterialClass, dict[str, Any]] = {
    "paint_body": {
        "Metallic": 0.0,
        "Roughness": 0.38,
        "Coat Weight": 1.0,
        "Coat Roughness": 0.05,
        "Alpha": 1.0,
    },
    "chrome": {
        "Base Color": (0.55, 0.55, 0.55, 1.0),
        "Metallic": 1.0,
        "Roughness": 0.05,
        "Coat Weight": 0.0,
        "Alpha": 1.0,
    },
    "chrome_trim": {
        "Base Color": (0.55, 0.55, 0.55, 1.0),
        "Metallic": 1.0,
        "Roughness": 0.08,
        "Coat Weight": 0.0,
        "Alpha": 1.0,
    },
    "rim_alloy": {
        "Metallic": 1.0,
        "Roughness": 0.22,
        "Coat Weight": 0.0,
        "Alpha": 1.0,
    },
    "glass": {
        "Base Color": (1.0, 1.0, 1.0, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.03,
        "Coat Weight": 0.0,
        "Transmission Weight": 1.0,
        "IOR": 1.52,
        "Alpha": 1.0,
    },
    "headlight_lens": {
        "Base Color": (1.0, 1.0, 1.0, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.08,
        "Transmission Weight": 0.9,
        "IOR": 1.55,
        "Alpha": 1.0,
    },
    "taillight_red": {
        "Base Color": (0.8, 0.05, 0.05, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.15,
        "Transmission Weight": 0.85,
        "IOR": 1.55,
        "Alpha": 1.0,
    },
    "tire_rubber": {
        "Base Color": (0.02, 0.02, 0.02, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.90,
        "Coat Weight": 0.0,
        "Alpha": 1.0,
    },
    "brake_rotor": {
        "Metallic": 1.0,
        "Roughness": 0.28,
        "Coat Weight": 0.0,
        "Alpha": 1.0,
    },
    "carbon_fiber": {
        "Metallic": 0.6,
        "Roughness": 0.32,
        "Coat Weight": 0.5,
        "Coat Roughness": 0.05,
        "Anisotropic": 0.8,
        "Alpha": 1.0,
    },
    "interior_plastic": {
        "Metallic": 0.0,
        "Roughness": 0.50,
        "Alpha": 1.0,
    },
    "leather_seat": {
        "Metallic": 0.0,
        "Roughness": 0.65,
        "Alpha": 1.0,
    },
    "default_plastic": {
        "Metallic": 0.0,
        "Roughness": 0.40,
        "Alpha": 1.0,
    },
}


# BSDF socket names in Blender 4.x. Used by classify_by_texture to look up
# the right input names when analyzing textures.
_BSDF_INPUTS: dict[str, str] = {
    "base_color": "Base Color",
    "metallic": "Metallic",
    "roughness": "Roughness",
    "ior": "IOR",
    "alpha": "Alpha",
    "normal": "Normal",
    "emission_color": "Emission Color",
    "emission_strength": "Emission Strength",
    "transmission_weight": "Transmission Weight",
    "coat_weight": "Coat Weight",
    "coat_roughness": "Coat Roughness",
    "coat_ior": "Coat IOR",
    "coat_tint": "Coat Tint",
    "anisotropic": "Anisotropic",
    "sheen_weight": "Sheen Weight",
    "sheen_roughness": "Sheen Roughness",
}


# Classes that are allowed to keep their emission value (for real bright lights).
_EMISSIVE_ALLOWED: frozenset[MaterialClass] = frozenset({"taillight_red"})


# Classes that need transparency (glass / lights) — get blend_method = "BLEND".
_TRANSPARENT_CLASSES: frozenset[MaterialClass] = frozenset(
    {"glass", "headlight_lens", "taillight_red"}
)


# Alpha values in this window get clamped to exactly 1.0 (Sketchfab "0.99" bug).
_ALPHA_CLAMP_MIN = 0.95
_ALPHA_CLAMP_MAX = 1.0

# Idempotence tolerance: skip a change if new value is within this of old.
_FLOAT_EPSILON = 1e-6


# ==========================================================================
# Helpers
# ==========================================================================


def _find_principled_bsdf(mat: MaterialLike) -> NodeLike | None:
    """Return the first Principled BSDF node in the material's node tree, or None."""
    if not mat.use_nodes or mat.node_tree is None:
        return None
    for node in mat.node_tree.nodes:
        if getattr(node, "type", None) == "BSDF_PRINCIPLED":
            return node  # type: ignore[no-any-return]
    return None


def _values_equal(a: Any, b: Any) -> bool:
    """Compare two socket values (float or tuple), with epsilon for floats."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < _FLOAT_EPSILON
    # Tuples / lists / colors
    if hasattr(a, "__len__") and hasattr(b, "__len__") and len(a) == len(b):
        return all(abs(float(x) - float(y)) < _FLOAT_EPSILON for x, y in zip(a, b, strict=True))
    return bool(a == b)


def _capture_value(sock: SocketLike) -> Any:
    """Return a hashable snapshot of a socket's default_value."""
    val = sock.default_value
    if hasattr(val, "__len__"):
        return tuple(float(x) for x in val)
    return float(val) if isinstance(val, (int, float)) else val


# ==========================================================================
# Pass 1 — name-based classification
# ==========================================================================


def classify_by_name(name: str) -> MaterialClass | None:
    """Return material class based on regex-match against name, or None.

    On conflict (multiple patterns match), the lowest priority number wins
    (most specific). Case-insensitive.
    """
    matches: list[tuple[int, MaterialClass]] = []
    for prio, cls, pat in _PATTERNS:
        if pat.search(name):
            matches.append((prio, cls))
    if not matches:
        return None
    matches.sort()
    return matches[0][1]


# ==========================================================================
# Pass 2 — texture-based classification
# ==========================================================================


def classify_by_texture(mat: MaterialLike, sampler: TextureSampler) -> MaterialClass | None:
    """Return material class based on texture-signal heuristics, or None.

    Analyzes the base-color and metallic-roughness textures downsampled to
    128×128. Uses per-channel means and std-deviations to detect solid
    black (tire), solid bright + metallic (chrome), red-tint (taillight),
    and transparency (glass).
    """
    if not mat.use_nodes or mat.node_tree is None:
        return None
    bc = sampler.sample(mat, _BSDF_INPUTS["base_color"], size=128)
    mr = sampler.sample(mat, _BSDF_INPUTS["metallic"], size=128)
    rg = sampler.sample(mat, _BSDF_INPUTS["roughness"], size=128)

    if bc is not None:
        rgb = bc[..., :3]
        avg = float(rgb.mean())
        std = float(rgb.std())
        # Solid black → tire
        if avg < 0.05 and std < 0.02:
            return "tire_rubber"
        # Bright + metallic map high → chrome
        if avg > 0.85 and mr is not None and float(mr.mean()) > 0.8:
            return "chrome"
        # Alpha channel present + low alpha → glass
        if bc.shape[-1] == 4 and float(bc[..., 3].mean()) < 0.5:
            return "glass"
        # Red-tint solid → taillight
        # (rough check: R >> G and R >> B, saturation > 0.5)
        r_avg = float(rgb[..., 0].mean())
        g_avg = float(rgb[..., 1].mean())
        b_avg = float(rgb[..., 2].mean())
        if r_avg > 0.5 and r_avg > 2 * g_avg and r_avg > 2 * b_avg:
            return "taillight_red"

    if mr is not None and rg is not None and float(mr.mean()) > 0.8 and float(rg.mean()) < 0.15:
        return "chrome"

    return None


# ==========================================================================
# Preset application (guarded)
# ==========================================================================


def apply_preset(mat: MaterialLike, cls: MaterialClass) -> list[ChangeRecord]:
    """Apply the PBR preset for `cls` to `mat`, respecting linked textures.

    A socket that has an incoming link (texture) is NOT overwritten (would
    break user's texture map). Exception: `Alpha` and `Emission Strength`
    are always overwritten because they are the most common Sketchfab bugs
    (0.99-alpha, base-color-in-emission-slot).
    """
    changes: list[ChangeRecord] = []
    bsdf = _find_principled_bsdf(mat)
    if bsdf is None:
        return changes

    preset = _PRESETS.get(cls, {})
    always_write = frozenset({"Alpha", "Emission Strength"})
    for input_name, target in preset.items():
        if input_name not in bsdf.inputs:
            continue
        sock = bsdf.inputs[input_name]
        # Skip if a texture is plugged in — unless it's a hard-fix input
        if sock.is_linked and input_name not in always_write:
            continue
        old = _capture_value(sock)
        if _values_equal(old, target):
            continue  # idempotent — no change needed
        sock.default_value = target
        changes.append(ChangeRecord(input_name=input_name, old=old, new=target, reason="preset"))
    return changes


# ==========================================================================
# Hard fixes — emission-kill, alpha-clamp, blend-mode
# ==========================================================================


def _apply_hard_fixes(mat: MaterialLike, cls: MaterialClass, changes: list[ChangeRecord]) -> None:
    """Apply hard fixes to a material regardless of classification success.

    Mutates `changes` in place, appending any additional records.
    """
    bsdf = _find_principled_bsdf(mat)
    if bsdf is None:
        return

    # 1. Emission-Kill: kill accidental emission on non-emissive classes
    if cls not in _EMISSIVE_ALLOWED:
        es_name = _BSDF_INPUTS["emission_strength"]
        if es_name in bsdf.inputs:
            es = bsdf.inputs[es_name]
            if not es.is_linked and float(es.default_value) > 0.0:
                old = _capture_value(es)
                es.default_value = 0.0
                changes.append(
                    ChangeRecord(input_name=es_name, old=old, new=0.0, reason="emission-kill")
                )
        # Also unlink emission-color if it's plugged (common Sketchfab bug:
        # base color dupe'd into emission slot).
        ec_name = _BSDF_INPUTS["emission_color"]
        if ec_name in bsdf.inputs:
            ec = bsdf.inputs[ec_name]
            if ec.is_linked and mat.node_tree is not None:
                # Find and remove the incoming link to Emission Color
                for link in list(mat.node_tree.links):
                    if getattr(link, "to_socket", None) is ec:
                        mat.node_tree.links.remove(link)
                        changes.append(
                            ChangeRecord(
                                input_name=ec_name,
                                old="linked",
                                new="unlinked",
                                reason="emission-kill",
                            )
                        )
                        break

    # 2. Alpha-Clamp: (0.95, 1.0) → 1.0 exactly (Sketchfab 0.99 bug)
    alpha_name = _BSDF_INPUTS["alpha"]
    if alpha_name in bsdf.inputs:
        alpha = bsdf.inputs[alpha_name]
        if not alpha.is_linked:
            val = float(alpha.default_value)
            if _ALPHA_CLAMP_MIN < val < _ALPHA_CLAMP_MAX:
                alpha.default_value = 1.0
                changes.append(
                    ChangeRecord(input_name=alpha_name, old=val, new=1.0, reason="alpha-clamp")
                )

    # 3. Blend-Mode-Consistency
    desired_blend: BlendMethod = "BLEND" if cls in _TRANSPARENT_CLASSES else "OPAQUE"
    if mat.blend_method != desired_blend:
        old_bm = mat.blend_method
        mat.blend_method = desired_blend
        changes.append(
            ChangeRecord(
                input_name="blend_method",
                old=old_bm,
                new=desired_blend,
                reason="blend-mode",
            )
        )


# ==========================================================================
# Top-level entry point
# ==========================================================================


def sanitize_materials(
    materials: Iterable[MaterialLike],
    sampler: TextureSampler | None = None,
) -> list[SanitizerReport]:
    """Normalize PBR values of all materials to cinema-grade defaults.

    Runs 3-pass classification (name → texture → default_plastic), then
    applies the class-preset, then hard-fixes. Materials are processed in
    name-sorted order for deterministic reporting.

    Args:
        materials: iterable of MaterialLike objects (bpy.types.Material).
        sampler: optional TextureSampler for Pass-2 texture-based
            classification. If None, Pass 2 is skipped and fall-through goes
            directly to `default_plastic`.

    Returns:
        Per-material report list.
    """
    # Materialize + sort deterministically (name order)
    mat_list = sorted(materials, key=lambda m: m.name)
    reports: list[SanitizerReport] = []

    for mat in mat_list:
        if not mat.use_nodes:
            reports.append(
                SanitizerReport(
                    material_name=mat.name,
                    classified_as="default_plastic",
                    source="default",
                    skipped_reason="use_nodes=False",
                )
            )
            continue

        # Pass 1 — name
        cls = classify_by_name(mat.name)
        source: ClassificationSource = "name"

        # Pass 2 — texture
        if cls is None and sampler is not None:
            cls = classify_by_texture(mat, sampler)
            if cls is not None:
                source = "texture"

        # Pass 3 — default
        if cls is None:
            cls = "default_plastic"
            source = "default"

        # Apply preset + hard-fixes
        changes: list[ChangeRecord] = apply_preset(mat, cls)
        _apply_hard_fixes(mat, cls, changes)

        reports.append(
            SanitizerReport(
                material_name=mat.name,
                classified_as=cls,
                source=source,
                changes=tuple(changes),
            )
        )

    return reports
