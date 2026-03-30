"""
MiroShark MCP Server

Exposes MiroShark simulation capabilities via the Model Context Protocol (MCP),
allowing Claude Code, Cursor, Windsurf, and any MCP-compatible agent to trigger
simulations, query results, and inspect agent states.

Tools:
  - list_simulations: List all simulations (optionally filtered by project)
  - create_simulation: Create a new simulation from a project
  - get_simulation_status: Get current status and run progress for a simulation
  - get_simulation_results: Get structured results (actions, agent stats, timeline)

Usage:
  python mcp_server.py              # stdio transport (default)
  python mcp_server.py --sse        # SSE transport on port 8765
"""

import os
import sys
import json
import argparse
from typing import Any

# Add backend root to path so app modules resolve
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server import Server
from mcp.server.stdio import run_stdio
from mcp.types import Tool, TextContent

from app.config import Config
from app.services.simulation_manager import SimulationManager, SimulationStatus
from app.services.simulation_runner import SimulationRunner
from app.models.project import ProjectManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _manager() -> SimulationManager:
    return SimulationManager()


def _json_response(data: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]


def _error(msg: str) -> list[TextContent]:
    return _json_response({"success": False, "error": msg})


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="list_simulations",
        description=(
            "List all MiroShark simulations. "
            "Optionally filter by project_id. Returns simulation ID, status, "
            "entity count, platform flags, and timestamps for each simulation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "Filter simulations by project ID (optional)",
                },
            },
        },
    ),
    Tool(
        name="create_simulation",
        description=(
            "Create a new MiroShark simulation for a given project. "
            "The project must already exist and have a built knowledge graph. "
            "Returns the new simulation_id which can be passed to other tools."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "string",
                    "description": "ID of the project to simulate (required)",
                },
                "enable_twitter": {
                    "type": "boolean",
                    "description": "Enable Twitter platform simulation (default true)",
                    "default": True,
                },
                "enable_reddit": {
                    "type": "boolean",
                    "description": "Enable Reddit platform simulation (default true)",
                    "default": True,
                },
                "enable_polymarket": {
                    "type": "boolean",
                    "description": "Enable Polymarket prediction market simulation (default false)",
                    "default": False,
                },
            },
            "required": ["project_id"],
        },
    ),
    Tool(
        name="get_simulation_status",
        description=(
            "Get the current status of a simulation including preparation progress, "
            "run state (current round, total rounds, progress percentage), "
            "platform statuses, and action counts."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "simulation_id": {
                    "type": "string",
                    "description": "The simulation ID to query (required)",
                },
            },
            "required": ["simulation_id"],
        },
    ),
    Tool(
        name="get_simulation_results",
        description=(
            "Get structured results from a simulation: agent actions (posts, likes, "
            "comments), per-agent statistics, simulation config, and timeline data. "
            "Use the optional parameters to filter by platform, agent, or round."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "simulation_id": {
                    "type": "string",
                    "description": "The simulation ID to query (required)",
                },
                "include_actions": {
                    "type": "boolean",
                    "description": "Include the full action log (default true)",
                    "default": True,
                },
                "include_agent_stats": {
                    "type": "boolean",
                    "description": "Include per-agent statistics (default true)",
                    "default": True,
                },
                "include_config": {
                    "type": "boolean",
                    "description": "Include the simulation configuration (default false)",
                    "default": False,
                },
                "include_timeline": {
                    "type": "boolean",
                    "description": "Include round-by-round timeline (default false)",
                    "default": False,
                },
                "platform": {
                    "type": "string",
                    "enum": ["twitter", "reddit"],
                    "description": "Filter results to a single platform (optional)",
                },
                "agent_id": {
                    "type": "integer",
                    "description": "Filter actions to a single agent ID (optional)",
                },
                "max_actions": {
                    "type": "integer",
                    "description": "Maximum number of actions to return (default 200)",
                    "default": 200,
                },
            },
            "required": ["simulation_id"],
        },
    ),
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_list_simulations(args: dict) -> list[TextContent]:
    manager = _manager()
    project_id = args.get("project_id")
    simulations = manager.list_simulations(project_id=project_id)

    results = []
    for sim in simulations:
        entry = sim.to_dict()
        # Attach lightweight run info if available
        run_state = SimulationRunner.get_run_state(sim.simulation_id)
        if run_state:
            entry["current_round"] = run_state.current_round
            entry["total_rounds"] = run_state.total_rounds
            entry["runner_status"] = run_state.runner_status.value
        results.append(entry)

    return _json_response({"success": True, "count": len(results), "simulations": results})


def handle_create_simulation(args: dict) -> list[TextContent]:
    project_id = args.get("project_id")
    if not project_id:
        return _error("project_id is required")

    project = ProjectManager.get_project(project_id)
    if not project:
        return _error(f"Project not found: {project_id}")

    graph_id = project.graph_id
    if not graph_id:
        return _error(
            f"Project {project_id} has no knowledge graph built yet. "
            "Build the graph first via the web UI or /api/graph/build endpoint."
        )

    manager = _manager()
    state = manager.create_simulation(
        project_id=project_id,
        graph_id=graph_id,
        enable_twitter=args.get("enable_twitter", True),
        enable_reddit=args.get("enable_reddit", True),
        enable_polymarket=args.get("enable_polymarket", False),
    )

    return _json_response({
        "success": True,
        "simulation_id": state.simulation_id,
        "project_id": state.project_id,
        "graph_id": state.graph_id,
        "status": state.status.value,
        "message": (
            f"Simulation {state.simulation_id} created. "
            "Next step: call the /api/simulation/prepare endpoint or use the web UI "
            "to prepare agent profiles and configuration before running."
        ),
    })


def handle_get_simulation_status(args: dict) -> list[TextContent]:
    simulation_id = args.get("simulation_id")
    if not simulation_id:
        return _error("simulation_id is required")

    manager = _manager()
    state = manager.get_simulation(simulation_id)
    if not state:
        return _error(f"Simulation not found: {simulation_id}")

    result = state.to_dict()

    # Enrich with runtime info
    run_state = SimulationRunner.get_run_state(simulation_id)
    if run_state:
        rd = run_state.to_dict()
        result["runner_status"] = rd.get("runner_status", "idle")
        result["current_round"] = rd.get("current_round", 0)
        result["total_rounds"] = rd.get("total_rounds", 0)
        result["progress_percent"] = rd.get("progress_percent", 0)
        result["twitter_actions_count"] = rd.get("twitter_actions_count", 0)
        result["reddit_actions_count"] = rd.get("reddit_actions_count", 0)
        result["total_actions_count"] = rd.get("total_actions_count", 0)
        result["started_at"] = rd.get("started_at")

    return _json_response({"success": True, "data": result})


def handle_get_simulation_results(args: dict) -> list[TextContent]:
    simulation_id = args.get("simulation_id")
    if not simulation_id:
        return _error("simulation_id is required")

    manager = _manager()
    state = manager.get_simulation(simulation_id)
    if not state:
        return _error(f"Simulation not found: {simulation_id}")

    result: dict[str, Any] = {
        "success": True,
        "simulation_id": simulation_id,
        "status": state.status.value,
    }

    platform = args.get("platform")
    agent_id = args.get("agent_id")
    max_actions = args.get("max_actions", 200)

    # Actions
    if args.get("include_actions", True):
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=max_actions,
            offset=0,
            platform=platform,
            agent_id=agent_id,
        )
        result["actions"] = [a.to_dict() for a in actions]
        result["actions_count"] = len(actions)

    # Agent stats
    if args.get("include_agent_stats", True):
        stats = SimulationRunner.get_agent_stats(simulation_id)
        result["agent_stats"] = stats
        result["agents_count"] = len(stats)

    # Config
    if args.get("include_config", False):
        config = manager.get_simulation_config(simulation_id)
        result["config"] = config

    # Timeline
    if args.get("include_timeline", False):
        timeline = SimulationRunner.get_timeline(simulation_id=simulation_id)
        result["timeline"] = timeline
        result["rounds_count"] = len(timeline)

    return _json_response(result)


HANDLER_MAP = {
    "list_simulations": handle_list_simulations,
    "create_simulation": handle_create_simulation,
    "get_simulation_status": handle_get_simulation_status,
    "get_simulation_results": handle_get_simulation_results,
}


# ---------------------------------------------------------------------------
# MCP Server setup
# ---------------------------------------------------------------------------

server = Server("miroshark")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = HANDLER_MAP.get(name)
    if not handler:
        return _error(f"Unknown tool: {name}")
    try:
        return handler(arguments)
    except Exception as e:
        return _error(f"Tool error ({name}): {str(e)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="MiroShark MCP Server")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport instead of stdio")
    parser.add_argument("--port", type=int, default=8765, help="Port for SSE transport (default 8765)")
    args = parser.parse_args()

    if args.sse:
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                await server.run(streams[0], streams[1], server.create_initialization_options())

        app = Starlette(routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
        ])

        uvicorn.run(app, host="0.0.0.0", port=args.port)
    else:
        async with run_stdio(server) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
