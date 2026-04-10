"""
miroshark CLI — entry point.

Registers all command groups and exposes the root Typer app.
Installed as `miroshark` via [project.scripts] in pyproject.toml.

Command tree:
  miroshark run          — full end-to-end variant test (main command)
  miroshark project      — ICP project management (list / build / show)
  miroshark variant      — run simulations on a pre-built project (test)
  miroshark results      — fetch and display simulation results (show)
  miroshark config       — CLI configuration (show / set / reset)
  miroshark runs         — list and delete past runs
"""

from __future__ import annotations

import typer

from .commands.run import app as run_app
from .commands.project import app as project_app
from .commands.variant import app as variant_app
from .commands.results import app as results_app
from .commands.config_cmd import app as config_app
from .commands.runs import app as runs_app
from . import __version__

# Root application
app = typer.Typer(
    name="miroshark",
    help=(
        "Variant testing via synthetic persona simulation.\n\n"
        "Quickstart:\n"
        "  miroshark run --icp icp.md --variants variants.json\n\n"
        "First run builds the ICP knowledge graph (~5-10 min). "
        "Subsequent runs reuse the cached graph (~20 sec)."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # let our print_error handle formatting
)


def _version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"miroshark {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """miroshark — agent-friendly synthetic persona variant simulation CLI."""


# Register command groups
app.add_typer(run_app, name="run")
app.add_typer(project_app, name="project")
app.add_typer(variant_app, name="variant")
app.add_typer(results_app, name="results")
app.add_typer(config_app, name="config")
app.add_typer(runs_app, name="runs")


def main() -> None:
    """Entry point called by [project.scripts]."""
    app()


if __name__ == "__main__":
    main()
