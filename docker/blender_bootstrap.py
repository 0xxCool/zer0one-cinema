"""Bootstrap for running zocinema inside Blender's bundled Python (Docker variant).

Blender's `-b -P` invocation loads this file and forwards arguments after `--`
on the command line to `sys.argv`. Click then consumes them as if `zocinema`
were called from a regular shell.

The `zer0one-cinema` package + its runtime deps are installed directly into
Blender's bundled Python (see Dockerfile), so `import zer0one_cinema.cli.main`
works with no sys.path manipulation.

This bootstrap is only invoked by the `/usr/local/bin/zocinema` wrapper; direct
usage: `blender -b -P /opt/zocinema/bootstrap.py -- model-prep car.glb ...`
"""
from __future__ import annotations

import sys

if "--" in sys.argv:
    user_args = sys.argv[sys.argv.index("--") + 1 :]
else:
    user_args = []

if not user_args:
    print(
        "usage: zocinema <subcommand> [args…]\n"
        "example: zocinema model-prep car.glb --output car_prepped.blend",
        file=sys.stderr,
    )
    sys.exit(2)

sys.argv = ["zocinema", *user_args]

from zer0one_cinema.cli.main import main  # noqa: E402

main()
