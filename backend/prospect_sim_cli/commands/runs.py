"""
prospect-sim runs — list, inspect, and delete past simulation runs.

Commands:
  runs list           List all past runs as a Rich table (or JSON with --quiet).
  runs show <id_or_n> Full inspection of one run: graph, agents, report outline.
  runs rm <id_or_n>   Delete all artifacts for a run (accepts project_id or row number).

Deletion removes:
  - Neo4j graph nodes/edges
  - Project, simulation, and report file directories
  - Local CLI cache entry

The backend must be running for all commands.
"""

from __future__ import annotations

import json
import sys
import textwrap
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..cache import IcpCache, CliConfig
from ..client import ApiClient, ApiError

app = typer.Typer(help="List and delete past simulation runs.")
console = Console()

# Orange brand colour used throughout the CLI
ORANGE = "#FF6B35"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_client() -> ApiClient:
    """Build ApiClient from CLI config."""
    config = CliConfig()
    return ApiClient(base_url=config.get("api_url") or "http://localhost:5001")


def _clear_cache_for_project(project_id: str) -> bool:
    """
    Remove the cache entry whose project_id matches the given value.

    IcpCache.delete() takes a SHA256 hash key, not a project_id.
    We iterate the cache dict to find the matching hash, then delete it.
    Returns True if an entry was found and removed.
    """
    cache = IcpCache()
    data = cache._load()

    # Find the hash whose value has the matching project_id
    hash_to_remove = None
    for file_hash, entry in data.items():
        if entry.get("project_id") == project_id:
            hash_to_remove = file_hash
            break

    if hash_to_remove:
        cache.delete(hash_to_remove)
        return True
    return False


def _resolve_project_id(identifier: str, client: "ApiClient") -> str:
    """
    Resolve a project_id from either a direct 'proj_...' string or a 1-based
    row number from `runs list`.  Raises typer.Exit(1) on any error.
    """
    if identifier.startswith("proj_"):
        return identifier

    try:
        row = int(identifier)
    except ValueError:
        console.print(f"[red]Error:[/red] {identifier!r} is not a project_id or row number.")
        raise typer.Exit(1)

    try:
        runs = client.get_runs()
    except ApiError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    if row < 1 or row > len(runs):
        console.print(f"[red]Error:[/red] Row {row} out of range (1–{len(runs)}).")
        raise typer.Exit(1)

    return runs[row - 1]["project_id"]


def _print_error(message: str, fix: str = "") -> None:
    """Print a machine-readable error and exit 1."""
    error = {"error": message}
    if fix:
        error["fix"] = fix
    console.print_json(json.dumps(error))
    raise typer.Exit(1)


def _render_runs_table(runs: list) -> None:
    """Render a Rich table of runs. Each run is one row."""
    table = Table(
        show_header=True,
        header_style=f"bold {ORANGE}",
        border_style="dim",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#",           justify="right", min_width=3,  style="dim")
    table.add_column("Name",        min_width=20)
    table.add_column("ICP file",    min_width=16, style="dim")
    table.add_column("Created",     min_width=16)
    table.add_column("Sims",        justify="right", min_width=4)
    table.add_column("Reports",     justify="right", min_width=7)
    table.add_column("Size",        justify="right", min_width=8)
    table.add_column("Project ID",  min_width=20, style="dim")

    for i, run in enumerate(runs, start=1):
        # Truncate the ICP filename for readability
        icp = run.get("icp_file", "—")
        if len(icp) > 22:
            icp = "…" + icp[-20:]

        # Format created_at: "2026-04-10T09:00:35" → "2026-04-10 09:00"
        created = run.get("created_at", "")
        if "T" in created:
            created = created.replace("T", " ")[:16]

        size_mb = run.get("disk_mb", 0)
        size_str = f"{size_mb:.1f} MB"

        name_text = Text(run.get("name", "—"))
        name_text.stylize(f"bold {ORANGE}")

        table.add_row(
            str(i),
            name_text,
            icp,
            created,
            str(run.get("total_simulations", 0)),
            str(run.get("total_reports", 0)),
            size_str,
            run.get("project_id", "—"),
        )

    console.print()
    console.print(table)
    console.print()


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command("list")
def runs_list(
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Output clean JSON only (pipeable).",
    ),
) -> None:
    """List all past simulation runs."""
    client = _make_client()

    try:
        runs = client.get_runs()
    except ApiError as exc:
        if quiet:
            _print_error(exc.message, exc.fix)
        console.print(f"[red]Error:[/red] {exc.message}")
        if exc.fix:
            console.print(f"[dim]Fix: {exc.fix}[/dim]")
        raise typer.Exit(1)

    if quiet:
        console.print_json(json.dumps(runs))
        return

    if not runs:
        console.print("[dim]No runs found.[/dim]")
        return

    _render_runs_table(runs)
    console.print(f"[dim]{len(runs)} run(s) total.[/dim]\n")


def _render_run_detail(detail: dict) -> None:
    """
    Render a full run inspection as a series of Rich panels.

    Sections:
      1. Project header (name, status, graph_id, requirement)
      2. Graph summary (node/edge counts + entity type bar chart)
      3. Per-simulation panel (agents table, LLM config, status)
      4. Per-report panel (title, summary, section list)
    """
    project = detail.get("project", {})
    graph = detail.get("graph") or {}
    simulations = detail.get("simulations", [])

    # ── 1. Project header ─────────────────────────────────────────────────
    meta = Table.grid(padding=(0, 2))
    meta.add_column(style=f"bold {ORANGE}", min_width=16)
    meta.add_column()

    status = project.get("status", "—")
    status_color = "green" if status == "graph_completed" else "yellow"

    meta.add_row("Name",       project.get("name", "—"))
    meta.add_row("Project ID", f"[dim]{project.get('project_id', '—')}[/dim]")
    meta.add_row("Status",     f"[{status_color}]{status}[/{status_color}]")
    meta.add_row("Created",    (project.get("created_at") or "—").replace("T", " ")[:19])
    meta.add_row("Graph ID",   f"[dim]{project.get('graph_id') or 'none'}[/dim]")
    if project.get("icp_file"):
        meta.add_row("ICP file", project["icp_file"])

    # Wrap the long requirement so it fits in the panel
    req = project.get("simulation_requirement") or ""
    if req:
        wrapped = textwrap.fill(req, width=72)
        meta.add_row("Requirement", f"[dim]{wrapped}[/dim]")

    console.print()
    console.print(Panel(meta, title=f"[bold {ORANGE}]Run Overview[/bold {ORANGE}]",
                        border_style=ORANGE, padding=(0, 2)))

    # ── 2. Graph ──────────────────────────────────────────────────────────
    if graph.get("error"):
        console.print(Panel(f"[red]Graph unavailable:[/red] {graph['error']}",
                            title=f"[dim]ICP Knowledge Graph[/dim]", border_style="dim"))
    elif graph:
        g_table = Table.grid(padding=(0, 3))
        g_table.add_column(style=f"bold {ORANGE}", min_width=8)
        g_table.add_column(style="dim")
        g_table.add_row(str(graph.get("node_count", 0)), "nodes")
        g_table.add_row(str(graph.get("edge_count", 0)),  "edges")

        entity_types = graph.get("entity_types", {})
        if entity_types:
            max_count = max(entity_types.values()) or 1
            bar_width = 16
            breakdown = Table(show_header=False, box=None, padding=(0, 1))
            breakdown.add_column(style=f"bold {ORANGE}", min_width=22)
            breakdown.add_column(justify="right", min_width=4)
            breakdown.add_column(min_width=18)
            for etype, count in entity_types.items():
                filled = int(bar_width * count / max_count)
                bar = Text()
                bar.append("█" * filled, style=f"bold {ORANGE}")
                bar.append("░" * (bar_width - filled), style="dim")
                breakdown.add_row(etype, str(count), bar)

            from rich.columns import Columns
            console.print(Panel(
                Columns([g_table, breakdown], padding=(0, 4)),
                title=f"[dim]ICP Knowledge Graph[/dim]",
                border_style=ORANGE,
            ))
        else:
            console.print(Panel(g_table, title=f"[dim]ICP Knowledge Graph[/dim]",
                                border_style=ORANGE))

    # ── 3 + 4. Simulations + reports ─────────────────────────────────────
    for i, sim in enumerate(simulations, start=1):
        sim_id = sim.get("simulation_id", "—")
        sim_status = sim.get("status", "—")
        sim_color = "green" if sim_status == "completed" else "yellow"

        # Agents table
        agents = sim.get("agents", [])
        agent_table = Table(show_header=True, header_style=f"bold {ORANGE}",
                            border_style="dim", show_lines=False, padding=(0, 1))
        agent_table.add_column("#",        justify="right", min_width=3,  style="dim")
        agent_table.add_column("Name",     min_width=20)
        agent_table.add_column("Type",     min_width=18, style="dim")
        agent_table.add_column("Activity", justify="right", min_width=8)
        agent_table.add_column("Stance",   min_width=10, style="dim")
        for ag in agents:
            agent_table.add_row(
                str(ag.get("id", "")),
                str(ag.get("name", "—")),
                str(ag.get("type", "—")),
                f"{ag.get('activity', 0):.1f}",
                str(ag.get("stance", "—")),
            )

        sim_meta = Table.grid(padding=(0, 2))
        sim_meta.add_column(style=f"bold {ORANGE}", min_width=14)
        sim_meta.add_column()
        sim_meta.add_row("Sim ID",   f"[dim]{sim_id}[/dim]")
        sim_meta.add_row("Status",   f"[{sim_color}]{sim_status}[/{sim_color}]")
        sim_meta.add_row("Rounds",   str(sim.get("total_rounds", 0)))
        sim_meta.add_row("Model",    str(sim.get("llm_model") or "—"))
        sim_meta.add_row("Base URL", f"[dim]{sim.get('llm_base_url') or '—'}[/dim]")
        sim_meta.add_row("Agents",   str(sim.get("agent_count", len(agents))))

        tp_count = len(sim.get("turning_points", []))
        if tp_count:
            sim_meta.add_row("Turning pts", str(tp_count))

        console.print(Panel(sim_meta,
                            title=f"[bold {ORANGE}]Simulation {i}[/bold {ORANGE}]",
                            border_style=ORANGE, padding=(0, 2)))
        console.print(Panel(agent_table,
                            title=f"[dim]Agents ({len(agents)})[/dim]",
                            border_style="dim"))

        # Report panels
        for j, rep in enumerate(sim.get("reports", []), start=1):
            rep_status = rep.get("status", "—")
            rep_color = "green" if rep_status == "completed" else "yellow"

            rep_meta = Table.grid(padding=(0, 2))
            rep_meta.add_column(style=f"bold {ORANGE}", min_width=12)
            rep_meta.add_column()
            rep_meta.add_row("Report ID", f"[dim]{rep.get('report_id', '—')}[/dim]")
            rep_meta.add_row("Status",    f"[{rep_color}]{rep_status}[/{rep_color}]")
            if rep.get("completed_at"):
                rep_meta.add_row("Completed", rep["completed_at"].replace("T", " ")[:19])

            if rep.get("title"):
                rep_meta.add_row("Title", f"[bold]{rep['title']}[/bold]")

            if rep.get("summary"):
                wrapped_summary = textwrap.fill(rep["summary"], width=68)
                rep_meta.add_row("Summary", f"[italic]{wrapped_summary}[/italic]")

            # Section list
            sections = rep.get("section_titles", [])
            if sections:
                section_text = Text()
                for k, title in enumerate(sections, start=1):
                    section_text.append(f"  {k}. ", style="dim")
                    section_text.append(title + "\n")
                rep_meta.add_row("Sections", section_text)

            console.print(Panel(rep_meta,
                                title=f"[bold {ORANGE}]Report {j}[/bold {ORANGE}]",
                                border_style=ORANGE, padding=(0, 2)))

    console.print()


@app.command("show")
def runs_show(
    identifier: str = typer.Argument(
        ...,
        help="Project ID (proj_...) OR row number from `runs list`.",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Output raw JSON (pipeable).",
    ),
) -> None:
    """Inspect a run in full — graph, agents, simulation status, report outline."""
    client = _make_client()

    # ── Resolve project_id ────────────────────────────────────────────────
    project_id: Optional[str] = None
    if identifier.startswith("proj_"):
        project_id = identifier
    else:
        try:
            row = int(identifier)
        except ValueError:
            console.print(f"[red]Error:[/red] {identifier!r} is not a project_id or row number.")
            raise typer.Exit(1)
        try:
            runs = client.get_runs()
        except ApiError as exc:
            console.print(f"[red]Error:[/red] {exc.message}")
            raise typer.Exit(1)
        if row < 1 or row > len(runs):
            console.print(f"[red]Error:[/red] Row {row} out of range (1–{len(runs)}).")
            raise typer.Exit(1)
        project_id = runs[row - 1]["project_id"]

    # ── Fetch detail ──────────────────────────────────────────────────────
    try:
        detail = client.get_run_detail(project_id)
    except ApiError as exc:
        if quiet:
            _print_error(exc.message, exc.fix)
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    if quiet:
        console.print_json(json.dumps(detail))
        return

    _render_run_detail(detail)


@app.command("graph")
def runs_graph(
    identifier: str = typer.Argument(..., help="Project ID or row number from `runs list`."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Output raw JSON."),
) -> None:
    """Show the ICP knowledge graph — nodes (entities) and edges (relationships)."""
    client = _make_client()
    project_id = _resolve_project_id(identifier, client)

    # Get graph_id via the run detail endpoint
    try:
        detail = client.get_run_detail(project_id)
    except ApiError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    graph_id = detail.get("project", {}).get("graph_id")
    if not graph_id:
        console.print("[red]Error:[/red] No graph built for this run.")
        raise typer.Exit(1)

    try:
        data = client.get_graph_data(graph_id)
    except ApiError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    if quiet:
        console.print_json(json.dumps(data))
        return

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    # ── Header stats ─────────────────────────────────────────────────────
    stats = Table.grid(padding=(0, 3))
    stats.add_column(style=f"bold {ORANGE}", min_width=6)
    stats.add_column(style="dim")
    stats.add_row(str(len(nodes)), "nodes")
    stats.add_row(str(len(edges)), "edges")
    console.print()
    console.print(Panel(stats,
                        title=f"[bold {ORANGE}]ICP Knowledge Graph[/bold {ORANGE}]  "
                              f"[dim]{graph_id[:16]}…[/dim]",
                        border_style=ORANGE, padding=(0, 2)))

    # ── Nodes table ───────────────────────────────────────────────────────
    node_table = Table(show_header=True, header_style=f"bold {ORANGE}",
                       border_style="dim", show_lines=True, padding=(0, 1))
    node_table.add_column("Type",    min_width=20, style=f"bold {ORANGE}")
    node_table.add_column("Name",    min_width=20)
    node_table.add_column("Summary", min_width=30, style="dim")

    for n in nodes:
        labels = n.get("labels") or []
        entity_type = labels[0] if labels else "—"
        name = n.get("name") or "—"
        summary = (n.get("summary") or "").strip()
        # Trim long summaries — they repeat the name
        if summary.startswith(name):
            summary = summary[len(name):].strip(" -()")
        node_table.add_row(entity_type, name, summary[:70] if summary else "—")

    console.print(Panel(node_table, title=f"[dim]Entities ({len(nodes)})[/dim]",
                        border_style=ORANGE))

    # ── Edges table ───────────────────────────────────────────────────────
    if edges:
        edge_table = Table(show_header=True, header_style=f"bold {ORANGE}",
                           border_style="dim", show_lines=True, padding=(0, 1))
        edge_table.add_column("Source",       min_width=16)
        edge_table.add_column("Relationship", min_width=20, style=f"bold {ORANGE}")
        edge_table.add_column("Target",       min_width=16)
        edge_table.add_column("Fact",         min_width=40, style="dim")

        for e in edges:
            edge_table.add_row(
                e.get("source_node_name") or "—",
                e.get("fact_type") or "—",
                e.get("target_node_name") or "—",
                (e.get("fact") or "")[:80],
            )

        console.print(Panel(edge_table, title=f"[dim]Relationships ({len(edges)})[/dim]",
                            border_style=ORANGE))

    console.print()


@app.command("report")
def runs_report(
    identifier: str = typer.Argument(..., help="Project ID or row number from `runs list`."),
    raw: bool = typer.Option(False, "--raw", help="Print raw markdown (pipeable)."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Output report JSON."),
) -> None:
    """Show the full simulation report — rendered or raw markdown."""
    from rich.markdown import Markdown

    client = _make_client()
    project_id = _resolve_project_id(identifier, client)

    try:
        detail = client.get_run_detail(project_id)
    except ApiError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    # Dig out the first report_id across simulations
    report_id = None
    for sim in detail.get("simulations", []):
        for rep in sim.get("reports", []):
            report_id = rep.get("report_id")
            if report_id:
                break
        if report_id:
            break

    if not report_id:
        console.print("[dim]No report found for this run.[/dim]")
        return

    try:
        report = client.get_report(report_id)
    except ApiError as exc:
        console.print(f"[red]Error:[/red] {exc.message}")
        raise typer.Exit(1)

    if quiet:
        console.print_json(json.dumps(report))
        return

    markdown_content = report.get("markdown_content") or ""

    if raw or not markdown_content:
        # Raw: just print the markdown text — pipeable to `less`, `bat`, etc.
        console.print(markdown_content or "[dim]Report is empty.[/dim]")
        return

    # Rendered: Rich Markdown in a panel
    project_name = detail.get("project", {}).get("name", project_id)
    console.print()
    console.print(Panel(
        Markdown(markdown_content),
        title=f"[bold {ORANGE}]Report — {project_name}[/bold {ORANGE}]",
        border_style=ORANGE,
        padding=(1, 2),
    ))
    console.print()


@app.command("rm")
def runs_rm(
    identifier: str = typer.Argument(
        ...,
        help="Project ID (e.g. proj_abc123) OR row number from `runs list`.",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Skip confirmation prompt (for unattended / scripted use).",
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q",
        help="Output clean JSON only (pipeable). Implies --yes.",
    ),
) -> None:
    """Delete all artifacts for a run (graph, files, cache entry)."""
    client = _make_client()

    # ── Resolve project_id ────────────────────────────────────────────────
    # Accept either a direct project_id or a row number from `runs list`.
    project_id: Optional[str] = None
    run_meta: Optional[dict] = None

    if identifier.startswith("proj_"):
        # Looks like a project_id — fetch run list to get metadata for confirmation.
        project_id = identifier
        try:
            runs = client.get_runs()
        except ApiError as exc:
            if quiet:
                _print_error(exc.message, exc.fix)
            console.print(f"[red]Error:[/red] {exc.message}")
            raise typer.Exit(1)
        run_meta = next((r for r in runs if r["project_id"] == project_id), None)
        if run_meta is None:
            if quiet:
                _print_error(f"Project {project_id} not found in runs list.")
            console.print(f"[red]Error:[/red] Project [bold]{project_id}[/bold] not found.")
            raise typer.Exit(1)
    else:
        # Treat as a 1-based row number.
        try:
            row = int(identifier)
        except ValueError:
            if quiet:
                _print_error(
                    f"Invalid identifier: {identifier!r}",
                    "Pass a project_id (proj_...) or a row number from `runs list`.",
                )
            console.print(
                f"[red]Error:[/red] {identifier!r} is not a project_id or row number.\n"
                "[dim]Usage: prospect-sim runs rm <project_id|number>[/dim]"
            )
            raise typer.Exit(1)

        try:
            runs = client.get_runs()
        except ApiError as exc:
            if quiet:
                _print_error(exc.message, exc.fix)
            console.print(f"[red]Error:[/red] {exc.message}")
            raise typer.Exit(1)

        if row < 1 or row > len(runs):
            if quiet:
                _print_error(f"Row {row} out of range (1–{len(runs)}).")
            console.print(f"[red]Error:[/red] Row {row} is out of range (1–{len(runs)}).")
            raise typer.Exit(1)

        run_meta = runs[row - 1]
        project_id = run_meta["project_id"]

    # ── Confirm ───────────────────────────────────────────────────────────
    name = run_meta.get("name", project_id)
    n_sims = run_meta.get("total_simulations", 0)
    n_reports = run_meta.get("total_reports", 0)

    if not quiet and not yes:
        prompt = (
            f"Delete [bold {ORANGE}]{name}[/bold {ORANGE}] "
            f"([dim]{project_id}[/dim]) with "
            f"{n_sims} simulation(s) and {n_reports} report(s)?"
        )
        console.print(f"\n{prompt}")
        confirmed = typer.confirm("", default=False)
        if not confirmed:
            console.print("[dim]Aborted.[/dim]")
            raise typer.Exit(0)

    # ── Delete via backend ────────────────────────────────────────────────
    try:
        result = client.delete_run(project_id)
    except ApiError as exc:
        if quiet:
            _print_error(exc.message, exc.fix)
        console.print(f"[red]Error:[/red] {exc.message}")
        if exc.fix:
            console.print(f"[dim]Fix: {exc.fix}[/dim]")
        raise typer.Exit(1)

    # ── Clear local cache entry ───────────────────────────────────────────
    # The backend handles Neo4j + file deletion; we own the local cache.
    cache_cleared = _clear_cache_for_project(project_id)

    if quiet:
        console.print_json(json.dumps({**result, "cache_cleared": cache_cleared}))
        return

    sims_del = result.get("deleted_simulations", 0)
    reports_del = result.get("deleted_reports", 0)
    graph_del = result.get("graph_deleted", False)

    console.print(
        f"\n[bold {ORANGE}]Deleted:[/bold {ORANGE}] {name} ({project_id})\n"
        f"  [dim]simulations:[/dim] {sims_del}  "
        f"[dim]reports:[/dim] {reports_del}  "
        f"[dim]graph:[/dim] {'yes' if graph_del else 'no (offline?)'}  "
        f"[dim]cache:[/dim] {'cleared' if cache_cleared else 'not found'}\n"
    )
