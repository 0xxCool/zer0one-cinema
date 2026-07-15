"""CLI entry points for zocinema — Click-based commands.

Package structure:
    main.py       — `zocinema` root command + version + help
    model_prep.py — `zocinema model-prep <glb>` subcommand (needs bpy at runtime)

Deferred sub-commands (v0.2+): `preflight`, `render`, `verify`.
"""

from .main import main

__all__ = ["main"]
