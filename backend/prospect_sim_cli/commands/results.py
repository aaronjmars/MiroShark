"""
`prospect-sim results show` — fetch and display simulation results.

Generates a report for a completed simulation, then displays the ranking.
Can also show raw simulation status without generating a full report.

Rule 2: minimum viable output — table by default, JSON with --quiet.
Rule 5: fail fast with actionable errors.
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import Annotated

import typer

from ..client import ApiClient, ApiError
from ..cache import CliConfig
from ..output import (
    print_error, print_info, print_json,
    print_ranking_table, spinner,
)

app = typer.Typer(help="Fetch and display simulation results.")


@app.command("show")
def results_show(
    sim_id: Annotated[str, typer.Option("--sim-id", help="Simulation ID to fetch results for", show_default=False)],
    status_only: Annotated[bool, typer.Option("--status", help="Show run status only, skip report generation")] = False,
    quiet: Annotated[bool, typer.Option("--quiet")] = False,
    api_url: Annotated[str, typer.Option("--api-url", envvar="PROSPECT_SIM_API_URL", hidden=True)] = "",
) -> None:
    """
    Fetch and display results for a completed simulation.

    Generates a ReACT report and renders the variant ranking table.
    Use --status to check run status without generating a full report.

    Examples:
      prospect-sim results show --sim-id sim_abc123
      prospect-sim results show --sim-id sim_abc123 --status
      prospect-sim results show --sim-id sim_abc123 --quiet | jq '.winner'
    """
    config = CliConfig()
    resolved_url = api_url or config.get("api_url") or "http://localhost:5001"
    client = ApiClient(base_url=resolved_url)

    if not client.health_check():
        print_error(
            "backend_unavailable",
            f"Cannot connect to backend at {resolved_url}",
            fix="cd backend && uv run python run.py",
            exit_code=2,
        )

    try:
        if status_only:
            # Lightweight status check — no report generation
            from ..client import SIMULATION_TIMEOUT
            status = client._get(f"/api/simulation/{sim_id}/run-status")
            if quiet:
                print_json(status)
            else:
                typer.echo(f"\nSimulation: {sim_id}")
                typer.echo(f"  Status: {status.get('status', 'unknown')}")
                if status.get("completed_rounds") is not None:
                    typer.echo(f"  Rounds: {status.get('completed_rounds')}/{status.get('total_rounds', '?')}")
                typer.echo()
            return

        # Full report generation
        print_info("Generating variant ranking report...", quiet)
        with spinner("Running ReACT report agent...", quiet):
            report_id = client.generate_report(sim_id)
            report = client.poll_report(report_id)

        ranking = report.get("ranking", [])
        failure_points = report.get("failure_points", {})

        results = {
            "winner": ranking[0].get("label") if ranking else None,
            "ranking": ranking,
            "failure_points": failure_points,
            "report_content": report.get("content", ""),
            "simulation_id": sim_id,
        }

        if quiet:
            print_json(results)
        else:
            print_ranking_table(results["ranking"], results["failure_points"])
            if results.get("winner"):
                typer.echo(f"\n🏆 Winner: {results['winner']}\n")

    except ApiError as exc:
        print_error(exc.code, exc.message, exc.fix, exc.docs, exit_code=2)
