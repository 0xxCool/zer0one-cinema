"""Bootstrap script for running `zocinema` inside Blender's bundled Python.

Blender's `-b -P` invocation loads this file and forwards the arguments
that come after `--` on the command line to `sys.argv` — click then
consumes them as if it were called from a regular shell.

Usage:
    blender -b -P scripts/run_zocinema.py -- <zocinema-args>

Example:
    blender -b -P scripts/run_zocinema.py -- model-prep car.glb \\
        --output car_prepped.blend --report report.json
"""
from __future__ import annotations

import site
import sys
from pathlib import Path

# Blender's bundled Python doesn't consult the user site (~/.local/lib/pythonX.Y)
# by default. We rely on ~/.local for third-party deps (click, numpy, sklearn)
# because installing into Blender's own site-packages is invasive and
# unnecessary — the user site is just as available at runtime.
site.ENABLE_USER_SITE = True
_user_site = site.getusersitepackages()
if _user_site not in sys.path:
    sys.path.insert(0, _user_site)

# Make the sibling `zer0one_cinema` package importable from inside Blender.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Blender puts its own args (e.g. `-b`, `-P`, this script's path) BEFORE the
# `--` separator, and user args AFTER. Extract the user args.
if "--" in sys.argv:
    dash_idx = sys.argv.index("--")
    user_args = sys.argv[dash_idx + 1 :]
else:
    user_args = []

if not user_args:
    print(
        "usage: blender -b -P scripts/run_zocinema.py -- <zocinema args>\n"
        "example: blender -b -P scripts/run_zocinema.py -- model-prep car.glb -o out.blend"
    )
    sys.exit(2)

# Rewrite sys.argv to look like a plain `zocinema` invocation so click sees
# the right prog name and argv.
sys.argv = ["zocinema", *user_args]

from zer0one_cinema.cli.main import main  # noqa: E402

main()
