"""
`prospect-sim run` — end-to-end variant test command.

The main command. Accepts an ICP file and a variants JSON file,
builds the graph (or reuses cache), runs simulations, generates report.

Rule 1: non-interactive — all config via flags, no prompts unless --yes skips them.
Rule 7: --dry-run shows the full plan without executing.
Rule 8: --yes bypasses confirmation for expensive operations.
"""

from __future__ import annotations

import json
import sys
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

app = typer.Typer(help="Run a full variant test: build ICP graph + simulate + rank.")


def _load_variants(variants_path: Path) -> list[dict]:
    """Parse and validate variants JSON file."""
    try:
        data = json.loads(variants_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print_error(
            "invalid_variants_file",
            f"Could not parse variants file: {exc}",
            fix=f"Ensure {variants_path} is valid JSON. See docs/WHAT_PROSPECT_SIM_PREDICTS.md",
            docs="prospect-sim variant test --help",
            exit_code=1,
        )
    if not isinstance(data, list) or not data:
        print_error(
            "invalid_variants_format",
            "Variants file must be a non-empty JSON array",
            fix='Format: [{"id":1,"label":"...","subject_line":"...","body":"...","hook_type":"problem"}]',
            exit_code=1,
        )
    if len(data) > 6:
        print_error(
            "too_many_variants",
            f"Maximum 6 variants per run ({len(data)} provided)",
            exit_code=1,
        )
    return data


def _print_dry_run_plan(
    icp: Path,
    variants: list[dict],
    icp_hash: str,
    cached_project_id: Optional[str],
    rounds: int,
    parallel: bool,
) -> None:
    """
    Print what would happen without executing anything.
    Rule 7: --dry-run mode.
    """
    cache_status = f"✓ cached ({cached_project_id})" if cached_project_id else "✗ not cached — will build"
    mode = "parallel" if parallel else "sequential"

    typer.echo(f"\n[dry-run] prospect-sim run")
    typer.echo(f"  ICP file:    {icp}")
    typer.echo(f"  ICP hash:    {icp_hash[:12]}...")
    typer.echo(f"  Graph:       {cache_status}")
    typer.echo(f"  Variants:    {len(variants)}")
    for v in variants:
        typer.echo(f"    [{v.get('hook_type','?')}] {v.get('label','?')}")
    typer.echo(f"  Rounds:      {rounds}")
    typer.echo(f"  Run mode:    {mode}")
    build_time = "~30 sec (cached)" if cached_project_id else "~5-10 min (graph build)"
    typer.echo(f"  Est. time:   {build_time} + ~{rounds * len(variants) * 2} sec simulation")
    typer.echo(f"\nRun without --dry-run to execute.\n")


def _build_icp_graph(
    client: ApiClient,
    cache: IcpCache,
    icp: Path,
    icp_hash: str,
    quiet: bool,
) -> str:
    """
    Upload ICP file, generate ontology, build graph, cache project_id.
    Returns project_id.
    """
    project_name = icp.stem.replace("-", " ").replace("_", " ").title()
    requirement = (
        "Test B2B cold email copy variants against HR Director / Head of People personas. "
        "Focus on open rate, reply intent, and dropout point analysis."
    )

    # Step 1: upload + ontology
    print_info("Uploading ICP file and generating ontology...", quiet)
    with spinner("Generating ontology...", quiet):
        ontology_result = client.generate_ontology(icp, project_name, requirement)

    project_id = ontology_result.get("project_id")
    if not project_id:
        print_error("missing_project_id", "Backend did not return a project_id after ontology generation")

    print_info(f"Project created: {project_id}", quiet)

    # Step 2: build graph
    print_info("Building knowledge graph (this takes a few minutes on first run)...", quiet)
    with spinner("Building graph...", quiet):
        task_id = client.build_graph(project_id)
        client.poll_task(task_id)

    # Cache the project_id so next run skips this step
    cache.set(icp_hash, project_id, str(icp.resolve()))
    print_success(f"Graph built and cached. Future runs will reuse project {project_id}", quiet)

    return project_id


def _run_simulations(
    client: ApiClient,
    project_id: str,
    variants: list[dict],
    simulation_requirement: str,
    parallel: bool,
    rounds: int,
    quiet: bool,
) -> list[dict]:
    """
    Create, prepare, start, and poll all variant simulations.
    Returns list of completed run_id dicts.
    """
    # Create simulations
    print_info(f"Creating {len(variants)} simulation(s)...", quiet)
    run_ids = client.run_variant_test(
        project_id, variants, simulation_requirement, parallel, rounds,
    )

    # Prepare and start each simulation
    for entry in run_ids:
        sim_id = entry["simulation_id"]
        label = entry.get("variant_label", sim_id)
        print_info(f"Preparing simulation for '{label}'...", quiet)
        with spinner(f"Preparing '{label}'...", quiet):
            task_id = client.prepare_simulation(sim_id)
            client.poll_task(task_id, timeout=300)  # 5 min prep timeout
        client.start_simulation(sim_id)
        print_info(f"Started simulation for '{label}'", quiet)

    # Poll all simulations until complete
    print_info(f"Running {len(run_ids)} simulation(s) ({rounds} rounds each)...", quiet)
    for entry in run_ids:
        sim_id = entry["simulation_id"]
        label = entry.get("variant_label", sim_id)
        with spinner(f"Simulating '{label}'...", quiet):
            client.poll_simulation(sim_id)
        print_success(f"Simulation complete: '{label}'", quiet)

    return run_ids


def _generate_and_fetch_report(
    client: ApiClient,
    run_ids: list[dict],
    quiet: bool,
) -> dict:
    """
    Generate report for the first (or best) simulation and return it.
    Uses the first simulation_id as the primary report target.
    """
    primary_sim_id = run_ids[0]["simulation_id"]
    print_info("Generating variant ranking report...", quiet)
    with spinner("Running ReACT report agent...", quiet):
        report_id = client.generate_report(primary_sim_id)
        report = client.poll_report(report_id)
    return report


def _format_results(report: dict, run_ids: list[dict]) -> dict:
    """
    Extract clean ranking + failure_points from raw report.
    Falls back to raw content if structured data is missing.
    """
    # The report agent may return structured data or free-text sections
    ranking = report.get("ranking", [])
    failure_points = report.get("failure_points", {})

    # If no structured ranking, build a basic one from simulation IDs
    if not ranking:
        ranking = [
            {
                "variant_id": str(entry.get("variant_id", i)),
                "label": entry.get("variant_label", f"Variant {i+1}"),
                "hook_type": entry.get("hook_type", "unknown"),
                "open_score": "n/a",
                "reply_score": "n/a",
            }
            for i, entry in enumerate(run_ids)
        ]

    return {
        "winner": ranking[0].get("label") if ranking else None,
        "ranking": ranking,
        "failure_points": failure_points,
        "report_content": report.get("content", ""),
        "simulation_ids": [e["simulation_id"] for e in run_ids],
    }


@app.callback(invoke_without_command=True)
def run(
    icp: Annotated[Path, typer.Option("--icp", help="ICP profile file (MD/TXT/PDF)", show_default=False)],
    variants: Annotated[Path, typer.Option("--variants", help="Variants JSON file", show_default=False)],
    rounds: Annotated[int, typer.Option("--rounds", help="Simulation rounds per variant")] = 8,
    parallel: Annotated[bool, typer.Option("--parallel/--sequential", help="Run variants in parallel or sequentially")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show execution plan without running")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Output clean JSON only (pipeable)")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompts (unattended)")] = False,
    api_url: Annotated[str, typer.Option("--api-url", envvar="PROSPECT_SIM_API_URL", help="Backend URL", hidden=True)] = "",
) -> None:
    """
    Run a full B2B cold email variant test.

    Builds ICP knowledge graph (cached after first run), simulates each email
    variant against synthetic decision-maker personas, and ranks by reply intent.

    Examples:
      prospect-sim run --icp icp.md --variants variants.json
      prospect-sim run --icp icp.md --variants variants.json --parallel --rounds 12
      prospect-sim run --icp icp.md --variants variants.json --dry-run
      prospect-sim run --icp icp.md --variants variants.json --quiet | jq '.winner'
    """
    # Resolve API URL (flag > env > config file)
    config = CliConfig()
    resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
    # Ontology generation can take 60-90s with local LLMs — use a generous timeout
    client = ApiClient(base_url=resolved_url, timeout=120)
    cache = IcpCache()

    # ── Validate inputs ──────────────────────────────────────────────────
    if not icp.exists():
        print_error("icp_file_not_found", f"ICP file not found: {icp}", exit_code=1)
    if not variants.exists():
        print_error("variants_file_not_found", f"Variants file not found: {variants}", exit_code=1)

    variants_data = _load_variants(variants)
    icp_hash = cache.hash_file(icp)

    # ── Cache check ──────────────────────────────────────────────────────
    cached_entry = cache.get(icp_hash)
    cached_project_id: Optional[str] = None

    if cached_entry:
        cached_project_id = cached_entry["project_id"]
        # Verify project still exists on backend
        try:
            client.get_project(cached_project_id)
            print_info(f"[cache hit] reusing project {cached_project_id}", quiet)
        except ApiError:
            # Project was deleted from backend — invalidate cache
            print_info(f"[cache miss] cached project {cached_project_id} no longer exists — rebuilding", quiet)
            cache.delete(icp_hash)
            cached_project_id = None

    # ── Dry run ──────────────────────────────────────────────────────────
    if dry_run:
        _print_dry_run_plan(icp, variants_data, icp_hash, cached_project_id, rounds, parallel)
        raise typer.Exit(0)

    # ── Backend health check ─────────────────────────────────────────────
    if not client.health_check():
        print_error(
            "backend_unavailable",
            f"Cannot connect to backend at {resolved_url}",
            fix="cd backend && uv run python run.py",
            docs="prospect-sim config set api-url <url>",
            exit_code=2,
        )

    # ── Phase 1: ICP graph build (skip if cached) ─────────────────────────
    project_id = cached_project_id
    if not project_id:
        if not yes:
            typer.confirm(
                f"Build ICP graph for {icp.name}? (takes ~5-10 min on first run)",
                default=True,
                abort=True,
            )
        try:
            project_id = _build_icp_graph(client, cache, icp, icp_hash, quiet)
        except ApiError as exc:
            print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    # ── Phase 2: Variant simulations ─────────────────────────────────────
    simulation_requirement = (
        "Rank email copy variants by reply intent. Identify dropout points "
        "(subject_line / opening / body / cta) for each variant."
    )
    try:
        run_ids = _run_simulations(
            client, project_id, variants_data,
            simulation_requirement, parallel, rounds, quiet,
        )
    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    # ── Phase 3: Report ──────────────────────────────────────────────────
    try:
        report = _generate_and_fetch_report(client, run_ids, quiet)
    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)

    # ── Output results ───────────────────────────────────────────────────
    results = _format_results(report, run_ids)

    if quiet:
        print_json(results)
    else:
        print_ranking_table(results["ranking"], results["failure_points"])
        if results.get("winner"):
            typer.echo(f"\n🏆 Winner: {results['winner']}\n")
