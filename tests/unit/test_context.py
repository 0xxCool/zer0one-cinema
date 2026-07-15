"""Unit tests for Context / TraceEntry / provenance_hash."""
from __future__ import annotations

from zer0one_cinema.context import Context, TraceEntry


def test_context_defaults() -> None:
    ctx = Context()
    assert ctx.scene_ref is None
    assert ctx.config == {}
    assert ctx.trace == []
    assert ctx.seed == 0
    assert ctx.version == "0.0.1"


def test_context_log_appends_trace_entry() -> None:
    ctx = Context()
    ctx.log("wheel_detect", "clustered_4_wheels", count=4, confidence=0.9)
    assert len(ctx.trace) == 1
    entry = ctx.trace[0]
    assert isinstance(entry, TraceEntry)
    assert entry.stage == "wheel_detect"
    assert entry.op == "clustered_4_wheels"
    assert entry.details == {"count": 4, "confidence": 0.9}


def test_context_log_multiple_entries_ordered() -> None:
    ctx = Context()
    ctx.log("s1", "op1")
    ctx.log("s2", "op2", key="value")
    ctx.log("s3", "op3", n=42)
    assert [e.stage for e in ctx.trace] == ["s1", "s2", "s3"]
    assert ctx.trace[2].details == {"n": 42}


def test_trace_entry_is_frozen() -> None:
    """TraceEntry is immutable — once logged, cannot be altered."""
    import pytest

    entry = TraceEntry(stage="s", op="o", details={})
    with pytest.raises(Exception):  # FrozenInstanceError
        entry.stage = "modified"  # type: ignore[misc]


def test_provenance_hash_deterministic() -> None:
    """Same inputs → identical hash."""
    ctx = Context(seed=42, version="1.2.3")
    h1 = ctx.provenance_hash("glb_sha", "preset_sha")
    h2 = ctx.provenance_hash("glb_sha", "preset_sha")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_provenance_hash_changes_on_input_change() -> None:
    ctx = Context(seed=42, version="1.0.0")
    baseline = ctx.provenance_hash("glb_A", "preset_A")
    assert ctx.provenance_hash("glb_B", "preset_A") != baseline  # different GLB
    assert ctx.provenance_hash("glb_A", "preset_B") != baseline  # different preset

    ctx_different_seed = Context(seed=99, version="1.0.0")
    assert ctx_different_seed.provenance_hash("glb_A", "preset_A") != baseline

    ctx_different_version = Context(seed=42, version="2.0.0")
    assert ctx_different_version.provenance_hash("glb_A", "preset_A") != baseline


def test_provenance_hash_stable_across_context_instances() -> None:
    """Two separate Context objects with identical fields → identical hash."""
    ctx1 = Context(seed=7, version="0.1.0")
    ctx2 = Context(seed=7, version="0.1.0")
    assert ctx1.provenance_hash("x", "y") == ctx2.provenance_hash("x", "y")


def test_context_config_mutable() -> None:
    """config dict can be mutated in place (not a frozen dataclass field)."""
    ctx = Context()
    ctx.config["preset"] = "night_neon"
    assert ctx.config == {"preset": "night_neon"}
