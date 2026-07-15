"""Unit tests for material_sanitize — pure-python, no Blender needed.

Uses `MockMaterial` with a full mock BSDF-node tree so we can test the whole
sanitizer path (classify → preset → hard-fixes) end-to-end without bpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from zer0one_cinema.model_prep.material_sanitize import (
    ChangeRecord,
    _apply_hard_fixes,
    _capture_value,
    _values_equal,
    apply_preset,
    classify_by_name,
    classify_by_texture,
    sanitize_materials,
)

# ---------------------------------------------------------------------------
# Mock infrastructure
# ---------------------------------------------------------------------------


@dataclass
class MockSocket:
    """Stand-in for bpy.types.NodeSocket."""

    default_value: Any
    is_linked: bool = False


@dataclass
class MockNode:
    """Stand-in for a Principled BSDF node."""

    type: str = "BSDF_PRINCIPLED"
    inputs: dict[str, MockSocket] = field(default_factory=dict)


@dataclass
class MockLink:
    to_socket: MockSocket


class MockLinksList:
    """Mimics bpy.types.NodeLinks — iterable + `.remove()`."""

    def __init__(self) -> None:
        self._links: list[MockLink] = []

    def append(self, link: MockLink) -> None:
        self._links.append(link)

    def remove(self, link: MockLink) -> None:
        self._links.remove(link)

    def __iter__(self):
        return iter(self._links)


@dataclass
class MockNodeTree:
    nodes: list[MockNode] = field(default_factory=list)
    links: MockLinksList = field(default_factory=MockLinksList)


@dataclass
class MockMaterial:
    """Stand-in for bpy.types.Material."""

    name: str
    use_nodes: bool = True
    blend_method: str = "OPAQUE"
    node_tree: MockNodeTree | None = None


def _make_bsdf_material(
    name: str,
    *,
    inputs: dict[str, Any] | None = None,
    linked_inputs: set[str] | None = None,
    blend_method: str = "OPAQUE",
    use_nodes: bool = True,
) -> MockMaterial:
    """Build a MockMaterial with a Principled BSDF node populated with sockets.

    `inputs` is a dict of socket-name → default_value.  Missing values from
    the standard BSDF get sensible defaults.
    """
    linked = linked_inputs or set()
    defaults: dict[str, Any] = {
        "Base Color": (0.8, 0.8, 0.8, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.5,
        "IOR": 1.45,
        "Alpha": 1.0,
        "Normal": 0.0,
        "Emission Color": (0.0, 0.0, 0.0, 1.0),
        "Emission Strength": 0.0,
        "Transmission Weight": 0.0,
        "Coat Weight": 0.0,
        "Coat Roughness": 0.03,
        "Coat IOR": 1.5,
        "Coat Tint": (1.0, 1.0, 1.0, 1.0),
        "Anisotropic": 0.0,
        "Sheen Weight": 0.0,
        "Sheen Roughness": 0.5,
    }
    if inputs:
        defaults.update(inputs)
    sockets = {n: MockSocket(default_value=v, is_linked=(n in linked)) for n, v in defaults.items()}
    tree = MockNodeTree(nodes=[MockNode(type="BSDF_PRINCIPLED", inputs=sockets)])
    return MockMaterial(name=name, use_nodes=use_nodes, blend_method=blend_method, node_tree=tree)


class MockTextureSampler:
    """A texture sampler that returns pre-set arrays."""

    def __init__(self, samples: dict[str, np.ndarray | None] | None = None) -> None:
        self._samples = samples or {}

    def sample(self, material: MockMaterial, input_name: str, size: int) -> np.ndarray | None:
        return self._samples.get(input_name)


# ---------------------------------------------------------------------------
# Helpers — _values_equal, _capture_value
# ---------------------------------------------------------------------------


def test_values_equal_floats_within_epsilon() -> None:
    assert _values_equal(0.1, 0.1 + 1e-9)
    assert not _values_equal(0.1, 0.2)


def test_values_equal_tuples_within_epsilon() -> None:
    assert _values_equal((1.0, 2.0, 3.0), (1.0, 2.0, 3.0 + 1e-9))
    assert not _values_equal((1.0, 2.0), (1.0, 3.0))


def test_capture_value_snapshots_tuple() -> None:
    sock = MockSocket(default_value=(0.5, 0.6, 0.7, 1.0))
    snapshot = _capture_value(sock)
    assert snapshot == (0.5, 0.6, 0.7, 1.0)


# ---------------------------------------------------------------------------
# Pass 1 — classify_by_name (12 classes + conflict + no-match)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("windshield_glass", "glass"),
        ("Windshield", "glass"),
        ("chrome_trim_outer", "chrome"),  # chrome (20) wins over chrome_trim (120)
        ("Karosserie_Lack", "paint_body"),
        ("body_paint_red", "paint_body"),
        ("Reifen_vorne", "tire_rubber"),
        ("tire_FL", "tire_rubber"),
        ("brake_disc", "brake_rotor"),
        ("brake_rotor_front", "brake_rotor"),
        ("carbon_hood", "carbon_fiber"),
        ("Kohlefaser_Spoiler", "carbon_fiber"),
        ("rim_alloy_20inch", "rim_alloy"),
        ("Felge_hinten", "rim_alloy"),
        ("headlight_lens_LED", "headlight_lens"),
        ("Scheinwerfer", "headlight_lens"),
        ("taillight_red_left", "taillight_red"),
        ("Rueckleuchte", "taillight_red"),
        ("dashboard_plastic", "interior_plastic"),
        ("Innenraum_console", "interior_plastic"),
        ("seat_leather_black", "leather_seat"),
        ("Ledersitz", "leather_seat"),
        ("chrome_trim_side", "chrome"),  # chrome wins over chrome_trim on conflict
        ("Zierleiste_chrom", "chrome"),  # chrome/chrom wins
        ("side_molding_plastic", "chrome_trim"),  # only chrome_trim matches
    ],
)
def test_classify_by_name(name: str, expected: str) -> None:
    assert classify_by_name(name) == expected


def test_classify_by_name_no_match() -> None:
    assert classify_by_name("random_material_123") is None


def test_classify_by_name_case_insensitive() -> None:
    assert classify_by_name("GLASS_WINDOW") == "glass"
    assert classify_by_name("Body_Paint") == "paint_body"


def test_classify_by_name_conflict_prio_wins() -> None:
    # "carbon_brake_disc" matches brake (40) AND carbon (50) → brake wins
    assert classify_by_name("carbon_brake_disc") == "brake_rotor"


# ---------------------------------------------------------------------------
# Pass 2 — classify_by_texture (mock texture sampler)
# ---------------------------------------------------------------------------


def test_classify_by_texture_solid_black_is_tire() -> None:
    black_texture = np.zeros((128, 128, 4), dtype=np.float32)
    black_texture[..., 3] = 1.0  # opaque
    sampler = MockTextureSampler({"Base Color": black_texture})
    mat = _make_bsdf_material("unknown_mesh")
    assert classify_by_texture(mat, sampler) == "tire_rubber"


def test_classify_by_texture_bright_metallic_is_chrome() -> None:
    bright_bc = np.full((128, 128, 4), 0.9, dtype=np.float32)
    high_metallic = np.full((128, 128, 4), 0.95, dtype=np.float32)
    sampler = MockTextureSampler(
        {
            "Base Color": bright_bc,
            "Metallic": high_metallic,
        }
    )
    mat = _make_bsdf_material("unknown_mesh")
    assert classify_by_texture(mat, sampler) == "chrome"


def test_classify_by_texture_red_dominant_is_taillight() -> None:
    red_bc = np.zeros((128, 128, 4), dtype=np.float32)
    red_bc[..., 0] = 0.8  # R
    red_bc[..., 3] = 1.0  # alpha
    sampler = MockTextureSampler({"Base Color": red_bc})
    mat = _make_bsdf_material("unknown_mesh")
    assert classify_by_texture(mat, sampler) == "taillight_red"


def test_classify_by_texture_low_alpha_is_glass() -> None:
    glass_bc = np.zeros((128, 128, 4), dtype=np.float32)
    glass_bc[..., :3] = 0.9
    glass_bc[..., 3] = 0.3  # transparent
    sampler = MockTextureSampler({"Base Color": glass_bc})
    mat = _make_bsdf_material("unknown_mesh")
    assert classify_by_texture(mat, sampler) == "glass"


def test_classify_by_texture_no_signal_returns_none() -> None:
    sampler = MockTextureSampler({})  # no textures
    mat = _make_bsdf_material("unknown_mesh")
    assert classify_by_texture(mat, sampler) is None


def test_classify_by_texture_no_nodes_returns_none() -> None:
    sampler = MockTextureSampler({})
    mat = MockMaterial(name="legacy", use_nodes=False, node_tree=None)
    assert classify_by_texture(mat, sampler) is None


# ---------------------------------------------------------------------------
# apply_preset
# ---------------------------------------------------------------------------


def test_apply_preset_paint_body_sets_coat_weight() -> None:
    mat = _make_bsdf_material("body_1")
    changes = apply_preset(mat, "paint_body")
    input_names = {c.input_name for c in changes}
    assert "Coat Weight" in input_names
    assert "Roughness" in input_names
    # Verify actual value
    sockets = mat.node_tree.nodes[0].inputs
    assert sockets["Coat Weight"].default_value == 1.0
    assert sockets["Roughness"].default_value == 0.38


def test_apply_preset_chrome_sets_metallic_1() -> None:
    mat = _make_bsdf_material("chrome_bumper")
    apply_preset(mat, "chrome")
    sockets = mat.node_tree.nodes[0].inputs
    assert sockets["Metallic"].default_value == 1.0
    assert sockets["Roughness"].default_value == 0.05


def test_apply_preset_skips_linked_sockets() -> None:
    """A linked (texture) socket must NOT be overwritten by preset (except Alpha)."""
    mat = _make_bsdf_material("body_1", linked_inputs={"Roughness"})
    original_roughness = mat.node_tree.nodes[0].inputs["Roughness"].default_value
    changes = apply_preset(mat, "paint_body")
    # Roughness should NOT be in changes (linked)
    assert not any(c.input_name == "Roughness" for c in changes)
    # And the value is unchanged
    assert mat.node_tree.nodes[0].inputs["Roughness"].default_value == original_roughness


def test_apply_preset_idempotent_when_already_correct() -> None:
    """Second apply on same material yields empty change list."""
    mat = _make_bsdf_material("body_1")
    apply_preset(mat, "paint_body")
    second = apply_preset(mat, "paint_body")
    assert len(second) == 0


def test_apply_preset_returns_empty_when_no_bsdf() -> None:
    mat = MockMaterial(name="legacy", use_nodes=False, node_tree=None)
    assert apply_preset(mat, "paint_body") == []


# ---------------------------------------------------------------------------
# Hard fixes
# ---------------------------------------------------------------------------


def test_hard_fix_emission_kill_zeroes_emission() -> None:
    """Blown-out Sketchfab body material with emission_strength > 0 → clamp to 0."""
    mat = _make_bsdf_material("body_1", inputs={"Emission Strength": 1.5})
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "paint_body", changes)
    assert mat.node_tree.nodes[0].inputs["Emission Strength"].default_value == 0.0
    assert any(c.reason == "emission-kill" for c in changes)


def test_hard_fix_emission_kill_skips_taillight() -> None:
    """Taillight allowed to keep emission."""
    mat = _make_bsdf_material("taillight_1", inputs={"Emission Strength": 5.0})
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "taillight_red", changes)
    assert mat.node_tree.nodes[0].inputs["Emission Strength"].default_value == 5.0
    assert not any(c.reason == "emission-kill" for c in changes)


def test_hard_fix_alpha_clamp_099_to_1() -> None:
    """The infamous Sketchfab 0.99-alpha bug: → clamped to 1.0."""
    mat = _make_bsdf_material("body_1", inputs={"Alpha": 0.99})
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "paint_body", changes)
    assert mat.node_tree.nodes[0].inputs["Alpha"].default_value == 1.0
    assert any(c.reason == "alpha-clamp" for c in changes)


def test_hard_fix_alpha_clamp_leaves_low_alpha_alone() -> None:
    """Alpha 0.5 (real transparency) is NOT clamped — only the 0.95..1.0 window."""
    mat = _make_bsdf_material("glass_1", inputs={"Alpha": 0.5})
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "glass", changes)
    assert mat.node_tree.nodes[0].inputs["Alpha"].default_value == 0.5


def test_hard_fix_blend_mode_glass_gets_blend() -> None:
    mat = _make_bsdf_material("windshield", blend_method="OPAQUE")
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "glass", changes)
    assert mat.blend_method == "BLEND"
    assert any(c.input_name == "blend_method" for c in changes)


def test_hard_fix_blend_mode_body_gets_opaque() -> None:
    """A body material accidentally set to BLEND → snap back to OPAQUE."""
    mat = _make_bsdf_material("body_1", blend_method="BLEND")
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "paint_body", changes)
    assert mat.blend_method == "OPAQUE"


def test_hard_fix_unlinks_emission_color_bug() -> None:
    """Common Sketchfab bug: base-color duplicated into Emission Color slot."""
    mat = _make_bsdf_material("body_1", linked_inputs={"Emission Color"})
    ec_socket = mat.node_tree.nodes[0].inputs["Emission Color"]
    mat.node_tree.links.append(MockLink(to_socket=ec_socket))
    changes: list[ChangeRecord] = []
    _apply_hard_fixes(mat, "paint_body", changes)
    assert not any(link.to_socket is ec_socket for link in mat.node_tree.links)
    assert any(c.reason == "emission-kill" and c.input_name == "Emission Color" for c in changes)


# ---------------------------------------------------------------------------
# Top-level sanitize_materials — E2E
# ---------------------------------------------------------------------------


def test_sanitize_materials_returns_per_material_report() -> None:
    mats = [
        _make_bsdf_material("body_paint"),
        _make_bsdf_material("chrome_bumper"),
        _make_bsdf_material("tire_FL"),
    ]
    reports = sanitize_materials(mats)
    assert len(reports) == 3
    by_name = {r.material_name: r for r in reports}
    assert by_name["body_paint"].classified_as == "paint_body"
    assert by_name["chrome_bumper"].classified_as == "chrome"
    assert by_name["tire_FL"].classified_as == "tire_rubber"


def test_sanitize_materials_unknown_falls_to_default_plastic() -> None:
    """Whitelist principle: unknown material → default_plastic, NOT paint_body."""
    mat = _make_bsdf_material("random_geo_00042")
    reports = sanitize_materials([mat])
    assert reports[0].classified_as == "default_plastic"
    assert reports[0].source == "default"


def test_sanitize_materials_idempotent() -> None:
    """Running twice yields an empty second-report."""
    mats = [
        _make_bsdf_material("body_paint"),
        _make_bsdf_material("chrome_bumper"),
    ]
    sanitize_materials(mats)
    second = sanitize_materials(mats)
    for r in second:
        assert len(r.changes) == 0


def test_sanitize_materials_deterministic_order() -> None:
    """Same input in different order → same report order (by name)."""
    mats1 = [
        _make_bsdf_material("body_paint"),
        _make_bsdf_material("chrome_bumper"),
        _make_bsdf_material("tire_FL"),
    ]
    mats2 = list(reversed(mats1))
    r1 = sanitize_materials(mats1)
    r2 = sanitize_materials(mats2)
    assert [r.material_name for r in r1] == [r.material_name for r in r2]


def test_sanitize_materials_skips_use_nodes_false() -> None:
    mat = MockMaterial(name="legacy_mat", use_nodes=False, node_tree=None)
    reports = sanitize_materials([mat])
    assert reports[0].skipped_reason == "use_nodes=False"


def test_sanitize_materials_uses_texture_fallback_when_sampler_given() -> None:
    """No name match, but texture is solid-black → classified as tire_rubber."""
    black = np.zeros((128, 128, 4), dtype=np.float32)
    black[..., 3] = 1.0
    sampler = MockTextureSampler({"Base Color": black})
    mat = _make_bsdf_material("part_007")
    reports = sanitize_materials([mat], sampler=sampler)
    assert reports[0].classified_as == "tire_rubber"
    assert reports[0].source == "texture"


def test_sanitize_materials_fixes_alpha_clamp_e2e() -> None:
    """E2E: material with 0.99 alpha → after sanitize, alpha = 1.0.

    For materials that a preset covers (all 13 classes set Alpha=1.0), the
    fix comes from the preset step. The dedicated alpha-clamp hard-fix is a
    safety net for edge-cases where a preset doesn't touch Alpha — covered
    in `test_hard_fix_alpha_clamp_099_to_1`.
    """
    mat = _make_bsdf_material("body_paint", inputs={"Alpha": 0.99})
    reports = sanitize_materials([mat])
    assert mat.node_tree.nodes[0].inputs["Alpha"].default_value == 1.0
    # Either preset or alpha-clamp made the change
    changes = reports[0].changes
    alpha_change = next((c for c in changes if c.input_name == "Alpha"), None)
    assert alpha_change is not None
    assert alpha_change.new == 1.0


def test_sanitize_materials_kills_emission_on_body_e2e() -> None:
    """E2E: body material with emission_strength=2 → after sanitize, =0 and reported."""
    mat = _make_bsdf_material("body_paint", inputs={"Emission Strength": 2.0})
    reports = sanitize_materials([mat])
    assert mat.node_tree.nodes[0].inputs["Emission Strength"].default_value == 0.0
    changes = reports[0].changes
    assert any(c.reason == "emission-kill" for c in changes)
