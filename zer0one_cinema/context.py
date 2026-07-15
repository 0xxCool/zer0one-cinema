"""Context and trace primitives for zer0one-cinema pipelines.

Every model-prep / preflight / render / verify module accepts a `Context`
and returns updates via `Context.log()`. The context is the single place
where pipeline state, config, seeds, and the append-only trace live.

The provenance hash makes runs reproducible for audit: same GLB + same
preset + same version + same seed → same hash → identical output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class TraceEntry:
    """One append-only entry in the pipeline trace."""

    stage: str  # e.g. "wheel_detect"
    op: str  # e.g. "clustered_4_wheels"
    details: dict[str, Any]  # JSON-serializable per convention


@dataclass
class Context:
    """Mutable pipeline context, threaded through every stage.

    Attributes:
        scene_ref: opaque handle to a Blender scene (None when running unit tests).
        config: pipeline configuration (JSON-serializable), typically loaded from CLI + preset YAML.
        trace: append-only operation log; used for rollback and audit reports.
        seed: global RNG seed for deterministic runs.
        version: package version (populated by CLI at startup).
    """

    scene_ref: object | None = None
    config: dict[str, Any] = field(default_factory=dict)
    trace: list[TraceEntry] = field(default_factory=list)
    seed: int = 0
    version: str = "0.0.1"

    def log(self, stage: str, op: str, **details: Any) -> None:
        """Append a trace entry. Values must be JSON-serializable."""
        self.trace.append(TraceEntry(stage=stage, op=op, details=details))

    def provenance_hash(self, glb_sha256: str, preset_sha256: str) -> str:
        """Return the SHA-256 hash that identifies this run's inputs.

        Same GLB + same preset + same package-version + same seed → same hash.
        Recorded in every delivered `report.json`.
        """
        h = sha256()
        h.update(b"zer0one-cinema:v1\n")
        h.update(glb_sha256.encode())
        h.update(b"|")
        h.update(preset_sha256.encode())
        h.update(b"|")
        h.update(self.version.encode())
        h.update(b"|")
        h.update(str(self.seed).encode())
        return h.hexdigest()
