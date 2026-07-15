"""All gate thresholds in one place — the calibration surface.

Sourced from ~/zer0one-web/.claude/skills/cinema-grade-verification/references/
gate-thresholds.md. Tune here, not inside gate functions.
"""
from __future__ import annotations

# Filled in during Phase P2. This module is imported by gates.py and
# thresholds propagate as module-level constants so overriding for tests
# is a matter of monkey-patching a single dict.

THRESHOLDS: dict[str, float] = {}
