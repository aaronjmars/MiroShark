"""
`prospect-sim variant test` — run simulations for a set of email variants.

Lower-level than `prospect-sim run`: assumes the ICP graph is already built
and you have a project_id. Use `prospect-sim run` for the full end-to-end flow.

Rule 1: non-interactive — all config via flags.
Rule 6: idempotent — same inputs produce the same simulation set.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer

from ..client import ApiClient, ApiError
from ..cache import IcpCache, CliConfig
from ..output import (
    print_error, print_info, print_success, print_json,
    print_ranking_table, spinner,
)

app = typer.Typer(help="Run variant simulations against a pre-built ICP project.")


@app.command("test")
def variant_test(
    variants: Annotated[Path, typer.Option("--variants", help="Variants JSON file", show_default=False)],
    project_id: Annotated[Optional[str], typer.Option("--project-id", help="Project ID (use if you have it)")] = None,
    icp: Annotated[Optional[Path], typer.Option("--icp", help="ICP file to look up cached project")] = None,
    rounds: Annotated[int, typer.Option("--rounds", help="Simulation rounds per variant")] = 8,
    parallel: Annotated[bool, typer.Option("--parallel/--sequential")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
    api_url: Annotated[str, typer.Option("--api-url", envvar="MIROSHARK_API_URL", hidden=True)] = "",
) -> None:
    """
    Run simulations for a variants JSON file against a pre-built ICP project.

    Requires either --project-id or --icp (to look up the cached project).
    The ICP graph must already be built — run `prospect-sim project build` first.

    Outputs: list of simulation_ids (or JSON with --quiet).

    Examples:
      prospect-sim variant test --variants variants.json --icp icp.md
      prospect-sim variant test --variants variants.json --project-id proj_abc --parallel
      prospect-sim variant test --variants variants.json --icp icp.md --quiet | jq '.[]'
    """
    if not project_id and not icp:
        print_error(
            "missing_argument",
            "Provide --project-id or --icp to identify the target project",
            fix="prospect-sim variant test --variants variants.json --icp icp.md",
            exit_code=1,
        )

    if not variants.exists():
        print_error("variants_file_not_found", f"Variants file not found: {variants}", exit_code=1)

    # Parse variants
    try:
        variants_data = json.loads(variants.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print_error(
            "invalid_variants_file",
            f"Could not parse variants file: {exc}",
            fix=f"Ensure {variants} is valid JSON.",
            exit_code=1,
        )
    if not isinstance(variants_data, list) or not variants_data:
        print_error("invalid_variants_format", "Variants file must be a non-empty JSON array", exit_code=1)
    if len(variants_data) > 6:
        print_error(
            "too_many_variants",
            f"Maximum 6 variants per run ({len(variants_data)} provided)",
            exit_code=1,
        )

    config = CliConfig()
    resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
    client = ApiClient(base_url=resolved_url)
    cache = IcpCache()

    # Resolve project_id from ICP cache if needed
    resolved_project_id = project_id
    if not resolved_project_id and icp:
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
        resolved_project_id = entry["project_id"]
        print_info(f"[cache hit] using project {resolved_project_id}", quiet)

    # Backend health check
    if not client.health_check():
        print_error(
            "backend_unavailable",
            f"Cannot connect to backend at {resolved_url}",
            fix="cd backend && uv run python run.py",
            exit_code=2,
        )

    simulation_requirement = (
        "Rank email copy variants by reply intent. Identify dropout points "
        "(subject_line / opening / body / cta) for each variant."
    )

    try:
        print_info(f"Creating {len(variants_data)} simulation(s)...", quiet)
        run_ids = client.run_variant_test(
            resolved_project_id, variants_data, simulation_requirement, parallel, rounds,
        )

        for entry in run_ids:
            sim_id = entry["simulation_id"]
            label = entry.get("variant_label", sim_id)
            print_info(f"Preparing simulation for '{label}'...", quiet)
            with spinner(f"Preparing '{label}'...", quiet):
                task_id = client.prepare_simulation(sim_id)
                client.poll_task(task_id, timeout=300)
            client.start_simulation(sim_id)
            print_info(f"Started simulation for '{label}'", quiet)

        print_info(f"Running {len(run_ids)} simulation(s)...", quiet)
        for entry in run_ids:
            sim_id = entry["simulation_id"]
            label = entry.get("variant_label", sim_id)
            with spinner(f"Simulating '{label}'...", quiet):
                client.poll_simulation(sim_id)
            print_success(f"Simulation complete: '{label}'", quiet)

    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    if quiet:
        print_json(run_ids)
    else:
        typer.echo("\nSimulations complete. Run IDs:")
        for entry in run_ids:
            typer.echo(f"  {entry.get('variant_label', '?')} → {entry['simulation_id']}")
        typer.echo(f"\nRun: prospect-sim results show --sim-id {run_ids[0]['simulation_id']}\n")
