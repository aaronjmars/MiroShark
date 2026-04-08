"""
Output renderers for prospect-sim CLI.

Three modes:
  - table (default):  rich-formatted human-readable output
  - json (--quiet):   clean JSON to stdout only — pipeable via jq
  - error:            always to stderr, always machine-readable JSON

Rule 2: minimum viable output by default, --quiet for JSON.
Rule 5: errors always include fix + docs fields.
Rule 10: data on success, nothing on silence.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from typing import Any, Optional

import typer

# Use rich if available (comes with typer[all])
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    _RICH = True
except ImportError:
    _RICH = False

_console = Console() if _RICH else None
_err_console = Console(stderr=True) if _RICH else None


def print_json(data: Any) -> None:
    """Write clean JSON to stdout. No other text. Pipeable via jq."""
    sys.stdout.write(json.dumps(data, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()


def print_error(
    code: str,
    message: str,
    fix: str = "",
    docs: str = "",
    exit_code: int = 1,
) -> None:
    """
    Write structured error to stderr and exit.
    Always machine-readable — agents parse this.

    Rule 5: fail fast with actionable errors.
    """
    payload: dict[str, str] = {"error": code, "message": message}
    if fix:
        payload["fix"] = fix
    if docs:
        payload["docs"] = docs

    sys.stderr.write(json.dumps(payload, ensure_ascii=False))
    sys.stderr.write("\n")
    sys.stderr.flush()
    raise typer.Exit(code=exit_code)


def print_success(message: str, quiet: bool = False) -> None:
    """Print a success message — suppressed in --quiet mode."""
    if quiet:
        return
    if _RICH and _err_console:
        _err_console.print(f"[green]✓[/green] {message}")
    else:
        sys.stderr.write(f"✓ {message}\n")


def print_info(message: str, quiet: bool = False) -> None:
    """Print informational message to stderr — suppressed in --quiet mode."""
    if quiet:
        return
    if _RICH and _err_console:
        _err_console.print(f"[dim]{message}[/dim]")
    else:
        sys.stderr.write(f"  {message}\n")


def print_ranking_table(ranking: list[dict], failure_points: dict) -> None:
    """
    Render variant ranking as a rich table.
    Winner gets a trophy. Failure points color-coded.
    """
    if not _RICH or not _console:
        # Fallback: plain text
        for i, entry in enumerate(ranking):
            marker = "👑 WINNER" if i == 0 else f"  #{i + 1}"
            print(f"{marker}  {entry.get('label', entry.get('variant_id', '?'))}")
            print(f"      Open score:  {entry.get('open_score', 'n/a')}")
            print(f"      Reply score: {entry.get('reply_score', 'n/a')}")
            fp = failure_points.get(str(entry.get('variant_id', '')), 'n/a')
            print(f"      Dropout at:  {fp}")
        return

    table = Table(title="Variant Ranking", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Variant", min_width=20)
    table.add_column("Hook", min_width=10)
    table.add_column("Opens", justify="right")
    table.add_column("Replies", justify="right")
    table.add_column("Main Dropout", min_width=14)

    dropout_colors = {
        "subject_line": "red",
        "opening": "yellow",
        "body": "yellow",
        "cta": "cyan",
        "none": "green",
    }

    for i, entry in enumerate(ranking):
        rank = "👑 1" if i == 0 else f"  {i + 1}"
        vid = str(entry.get("variant_id", ""))
        dropout = failure_points.get(vid, "n/a")
        color = dropout_colors.get(dropout, "white")
        table.add_row(
            rank,
            entry.get("label", vid),
            entry.get("hook_type", "—"),
            str(entry.get("open_score", "—")),
            str(entry.get("reply_score", "—")),
            f"[{color}]{dropout}[/{color}]",
        )

    _console.print(table)


def print_project_table(projects: list[dict]) -> None:
    """Render cached ICP projects as a table."""
    if not projects:
        sys.stderr.write("No cached ICP projects found.\n")
        sys.stderr.write("Run: prospect-sim project build --icp <file>\n")
        return

    if not _RICH or not _console:
        for p in projects:
            print(f"{p.get('project_id', '?')}  {p.get('icp_file', '?')}  {p.get('created_at', '?')}")
        return

    table = Table(title="Cached ICP Projects", show_header=True, header_style="bold cyan")
    table.add_column("Project ID", min_width=16)
    table.add_column("ICP File", min_width=24)
    table.add_column("Cached At", min_width=20)

    for p in projects:
        table.add_row(
            p.get("project_id", "?"),
            p.get("icp_file", "?"),
            p.get("created_at", "?"),
        )
    _console.print(table)


@contextmanager
def spinner(label: str, quiet: bool = False):
    """
    Context manager showing a spinner during long operations.
    Suppressed in --quiet mode (agents don't read spinners).

    Usage:
        with spinner("Building ICP graph...", quiet=quiet):
            result = client.build_graph(...)
    """
    if quiet or not _RICH:
        yield
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=_err_console,
    ) as progress:
        progress.add_task(label, total=None)
        yield
