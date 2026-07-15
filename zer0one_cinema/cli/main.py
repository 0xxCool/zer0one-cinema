"""zocinema — Click-based CLI entry point.

Usage:
    zocinema --version
    zocinema model-prep <glb> --output <blend> [--report <json>] [--seed 0]
    zocinema preflight <blend> --camera <cam-name> [--max-iters 3]     (v0.2)
    zocinema verify <frames-dir> [--gates ...] [--strict]              (v0.2)

More commands (render) arrive in v0.3+.
"""

from __future__ import annotations

import click

from .. import __version__
from . import model_prep as _model_prep
from . import preflight as _preflight
from . import verify as _verify


@click.group()
@click.version_option(version=__version__, prog_name="zocinema")
def main() -> None:
    """zer0one-cinema — deterministic cinema-grade rendering automation.

    Every subcommand is designed to be reproducible: identical inputs +
    identical --seed produce byte-identical outputs.
    """


# Register sub-commands
main.add_command(_model_prep.model_prep_command, name="model-prep")
main.add_command(_preflight.preflight_command, name="preflight")
main.add_command(_verify.verify_command, name="verify")


if __name__ == "__main__":
    main()
