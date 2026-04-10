"""
`prospect-sim project` — ICP project management commands.

Sub-commands:
  list   List all cached ICP projects (reads local cache, no backend needed)
  build  Build the ICP knowledge graph for a file and cache the project_id
  show   Show details for a specific project

Rule 1: non-interactive — all config via flags.
Rule 6: idempotent — building the same ICP twice skips the build (cached).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer

from ..client import ApiClient, ApiError
from ..cache import IcpCache, CliConfig
from ..output import (
    print_error, print_info, print_success, print_json,
    print_project_table, spinner,
)

app = typer.Typer(help="Manage ICP knowledge graph projects.")


@app.command("list")
def project_list(
    quiet: Annotated[bool, typer.Option("--quiet", help="Output clean JSON only")] = False,
) -> None:
    """
    List all locally cached ICP projects.

    Reads ~/.miroshark/cache.json — no backend connection required.

    Examples:
      prospect-sim project list
      prospect-sim project list --quiet | jq '.[0].project_id'
    """
    cache = IcpCache()
    entries = cache.list_all()

    if quiet:
        print_json(entries)
    else:
        print_project_table(entries)


@app.command("build")
def project_build(
    icp: Annotated[Path, typer.Option("--icp", help="ICP profile file (MD/TXT/PDF)", show_default=False)],
    force: Annotated[bool, typer.Option("--force", "-f", help="Rebuild even if cached")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Output clean JSON only")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompts")] = False,
    api_url: Annotated[str, typer.Option("--api-url", envvar="MIROSHARK_API_URL", hidden=True)] = "",
) -> None:
    """
    Build the ICP knowledge graph and cache the project_id.

    This is the slow step (~5-10 min on first run). The result is cached by
    SHA256 of the ICP file — subsequent runs reuse the cached project instantly.

    Examples:
      prospect-sim project build --icp icp.md
      prospect-sim project build --icp icp.md --force   # rebuild even if cached
      prospect-sim project build --icp icp.md --yes     # skip confirmation
    """
    if not icp.exists():
        print_error("icp_file_not_found", f"ICP file not found: {icp}", exit_code=1)

    config = CliConfig()
    resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
    client = ApiClient(base_url=resolved_url)
    cache = IcpCache()

    icp_hash = cache.hash_file(icp)

    # Check cache first
    cached_entry = cache.get(icp_hash)
    if cached_entry and not force:
        project_id = cached_entry["project_id"]
        if quiet:
            print_json({"project_id": project_id, "cached": True, "icp_file": str(icp)})
        else:
            typer.echo(f"[cache hit] project {project_id} already built for {icp.name}")
            typer.echo("Use --force to rebuild.")
        raise typer.Exit(0)

    # Backend health check
    if not client.health_check():
        print_error(
            "backend_unavailable",
            f"Cannot connect to backend at {resolved_url}",
            fix="cd backend && uv run python run.py",
            docs="prospect-sim config set api-url <url>",
            exit_code=2,
        )

    # Confirmation
    if not yes:
        typer.confirm(
            f"Build ICP graph for {icp.name}? (takes ~5-10 min on first run)",
            default=True,
            abort=True,
        )

    # Build the graph
    project_name = icp.stem.replace("-", " ").replace("_", " ").title()
    requirement = "Simulate variants against target personas."

    try:
        print_info("Uploading ICP file and generating ontology...", quiet)
        with spinner("Generating ontology...", quiet):
            ontology_result = client.generate_ontology(icp, project_name, requirement)

        project_id = ontology_result.get("project_id")
        if not project_id:
            print_error("missing_project_id", "Backend did not return a project_id")

        print_info(f"Project created: {project_id}", quiet)
        print_info("Building knowledge graph...", quiet)

        with spinner("Building graph...", quiet):
            task_id = client.build_graph(project_id)
            client.poll_task(task_id)

        cache.set(icp_hash, project_id, str(icp.resolve()))
        print_success(f"Graph built and cached: {project_id}", quiet)

    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    if quiet:
        print_json({"project_id": project_id, "cached": True, "icp_file": str(icp)})


@app.command("show")
def project_show(
    project_id: Annotated[Optional[str], typer.Argument(help="Project ID to inspect")] = None,
    icp: Annotated[Optional[Path], typer.Option("--icp", help="Look up project by ICP file")] = None,
    quiet: Annotated[bool, typer.Option("--quiet", help="Output clean JSON only")] = False,
    api_url: Annotated[str, typer.Option("--api-url", envvar="MIROSHARK_API_URL", hidden=True)] = "",
) -> None:
    """
    Show details for a cached ICP project.

    Provide either a project_id argument or --icp to look up by file.

    Examples:
      prospect-sim project show proj_abc123
      prospect-sim project show --icp icp.md
    """
    if not project_id and not icp:
        print_error(
            "missing_argument",
            "Provide a project_id argument or --icp <file>",
            fix="prospect-sim project show proj_abc123  OR  prospect-sim project show --icp icp.md",
            exit_code=1,
        )

    cache = IcpCache()

    # Resolve project_id from ICP file if needed
    if icp and not project_id:
        if not icp.exists():
            print_error("icp_file_not_found", f"ICP file not found: {icp}", exit_code=1)
        icp_hash = cache.hash_file(icp)
        entry = cache.get(icp_hash)
        if not entry:
            print_error(
                "project_not_cached",
                f"No cached project for {icp.name}",
                fix="prospect-sim project build --icp <file>",
                exit_code=1,
            )
        project_id = entry["project_id"]

    # Fetch from backend for live status
    config = CliConfig()
    resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
    client = ApiClient(base_url=resolved_url)

    try:
        data = client.get_project(project_id)
    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    if quiet:
        print_json(data)
    else:
        typer.echo(f"\nProject: {project_id}")
        for k, v in data.items():
            typer.echo(f"  {k}: {v}")
        typer.echo()
