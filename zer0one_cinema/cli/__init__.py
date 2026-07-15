"""CLI entry points for zocinema — Click-based commands.

Package structure:
    main.py       — `zocinema` root command + version + help
    model_prep.py — `zocinema model-prep <glb>` subcommand (needs bpy at runtime)
    preflight.py  — `zocinema preflight <blend>`  (v0.2, needs bpy + cv2)
    verify.py     — `zocinema verify <frames>`    (v0.2, needs cv2)

Deferred sub-commands (v0.3+): `render`.
"""

from .main import main

__all__ = ["main"]
