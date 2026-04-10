"""
Runs API — list, inspect, and delete complete simulation runs.

A "run" is anchored to a project_id and includes:
  - project files      (uploads/projects/{project_id}/)
  - simulation files   (uploads/simulations/{sim_id}/)  — one or more per project
  - report files       (uploads/reports/{report_id}/)   — one per simulation
  - Neo4j graph        (identified by graph_id stored in project.json)
  - CLI cache entry    (not managed here — CLI clears its own cache on delete)

Endpoints:
  GET  /api/runs                       — list all runs, sorted newest first
  GET  /api/runs/<project_id>/detail   — full inspection: project + graph + sims + reports
  DELETE /api/runs/<project_id>        — delete every artifact for one run
"""

from __future__ import annotations

import json
import os
import shutil
import logging

from flask import current_app, jsonify

from . import runs_bp
from ..models.project import ProjectManager
from ..config import Config

logger = logging.getLogger(__name__)

# ── Path helpers ──────────────────────────────────────────────────────────────

# These mirror Config constants — resolved once at import time.
SIMULATIONS_DIR = Config.WONDERWALL_SIMULATION_DATA_DIR        # uploads/simulations/
REPORTS_DIR = os.path.join(Config.UPLOAD_FOLDER, "reports")   # uploads/reports/


def _dir_size_mb(path: str) -> float:
    """Sum all file sizes under path recursively; return megabytes (2 dp)."""
    total = 0
    for root, _, files in os.walk(path):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass  # file vanished between listdir and stat — skip
    return round(total / (1024 * 1024), 2)


def _simulations_for_project(project_id: str) -> list[dict]:
    """
    Scan uploads/simulations/ for entries that belong to project_id.
    Each simulation dir contains simulation_config.json with a project_id field.
    Returns list of dicts with {simulation_id, sim_dir, report_ids}.
    """
    if not os.path.isdir(SIMULATIONS_DIR):
        return []

    results = []
    for sim_id in os.listdir(SIMULATIONS_DIR):
        sim_dir = os.path.join(SIMULATIONS_DIR, sim_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        if not os.path.isfile(config_path):
            continue
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if cfg.get("project_id") == project_id:
            results.append({
                "simulation_id": sim_id,
                "sim_dir": sim_dir,
                "report_ids": _reports_for_simulation(sim_id),
            })

    return results


def _reports_for_simulation(simulation_id: str) -> list[dict]:
    """
    Scan uploads/reports/ for entries that belong to simulation_id.
    Each report dir contains meta.json with a simulation_id field.
    Returns list of {report_id, report_dir}.
    """
    if not os.path.isdir(REPORTS_DIR):
        return []

    results = []
    for report_id in os.listdir(REPORTS_DIR):
        report_dir = os.path.join(REPORTS_DIR, report_id)
        meta_path = os.path.join(report_dir, "meta.json")
        if not os.path.isfile(meta_path):
            continue
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        if meta.get("simulation_id") == simulation_id:
            results.append({"report_id": report_id, "report_dir": report_dir})

    return results


# ── Endpoints ─────────────────────────────────────────────────────────────────

@runs_bp.route("", methods=["GET"])
def list_runs():
    """
    GET /api/runs — list all projects with their simulations, reports, and disk usage.
    Returns list sorted by created_at descending (newest run first).
    """
    projects = ProjectManager.list_projects(limit=200)
    runs = []

    for project in projects:
        pid = project.project_id
        simulations = _simulations_for_project(pid)

        # Aggregate report count across all simulations
        all_report_ids = [
            r["report_id"]
            for sim in simulations
            for r in sim["report_ids"]
        ]

        # Disk: project dir + every simulation dir + every report dir
        total_size_mb = 0.0
        project_dir = ProjectManager._get_project_dir(pid)
        if os.path.isdir(project_dir):
            total_size_mb += _dir_size_mb(project_dir)
        for sim in simulations:
            total_size_mb += _dir_size_mb(sim["sim_dir"])
        for sim in simulations:
            for rep in sim["report_ids"]:
                total_size_mb += _dir_size_mb(rep["report_dir"])

        # Extract ICP filename from project files list (first file's original name)
        icp_file = ""
        if project.files:
            icp_file = project.files[0].get("original_filename", "")

        runs.append({
            "project_id": pid,
            "name": project.name,
            "created_at": project.created_at,
            "graph_id": project.graph_id,
            "icp_file": icp_file,
            "simulations": [
                {
                    "simulation_id": s["simulation_id"],
                    "report_ids": [r["report_id"] for r in s["report_ids"]],
                }
                for s in simulations
            ],
            "total_simulations": len(simulations),
            "total_reports": len(all_report_ids),
            "disk_mb": round(total_size_mb, 2),
        })

    logger.info("Listed %d runs", len(runs))
    return jsonify({"success": True, "data": runs})


@runs_bp.route("/<project_id>/detail", methods=["GET"])
def get_run_detail(project_id: str):
    """
    GET /api/runs/<project_id>/detail — full inspection of one run.

    Returns a single dict with:
      project   — metadata, status, simulation_requirement, graph_id
      graph     — node/edge counts + entity type breakdown from Neo4j
      simulations — per-simulation: agent list, status, rounds, LLM model, reports
    """
    project = ProjectManager.get_project(project_id)
    if project is None:
        return jsonify({"success": False, "error": f"Project {project_id} not found"}), 404

    # ── Graph data from Neo4j ─────────────────────────────────────────────
    graph_summary = None
    graph_id = project.graph_id
    if graph_id:
        storage = current_app.extensions.get("neo4j_storage")
        if storage:
            try:
                raw = storage.get_graph_data(graph_id)
                # Nodes carry a "labels" list (Neo4j multi-label).
                # Use the first label as the entity type for display.
                nodes = raw.get("nodes", [])
                from collections import Counter
                type_counts = Counter(
                    (n.get("labels") or ["unknown"])[0]
                    for n in nodes
                )
                graph_summary = {
                    "node_count": raw.get("node_count", len(nodes)),
                    "edge_count": raw.get("edge_count", 0),
                    "entity_types": dict(type_counts.most_common()),
                }
            except Exception as exc:
                logger.warning("Could not fetch graph data for %s: %s", graph_id, exc)
                graph_summary = {"error": str(exc)}

    # ── Simulations + reports ─────────────────────────────────────────────
    simulations_detail = []
    for sim_entry in _simulations_for_project(project_id):
        sim_id = sim_entry["simulation_id"]
        sim_dir = sim_entry["sim_dir"]

        # simulation_config.json — agents, LLM model, time config, requirement
        config_path = os.path.join(sim_dir, "simulation_config.json")
        sim_cfg = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    sim_cfg = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        # env_status.json — running status + pid
        status_path = os.path.join(sim_dir, "env_status.json")
        sim_status = {}
        if os.path.isfile(status_path):
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    sim_status = json.load(f)
            except (OSError, json.JSONDecodeError):
                pass

        # trajectory.json — total_rounds, turning_points
        traj_path = os.path.join(sim_dir, "trajectory.json")
        total_rounds = 0
        turning_points = []
        if os.path.isfile(traj_path):
            try:
                with open(traj_path, "r", encoding="utf-8") as f:
                    traj = json.load(f)
                total_rounds = traj.get("total_rounds", 0)
                turning_points = traj.get("turning_points", [])
            except (OSError, json.JSONDecodeError):
                pass

        # Slim down agent list to what's useful for inspection
        agents = [
            {
                "id": a.get("agent_id"),
                "name": a.get("entity_name"),
                "type": a.get("entity_type"),
                "activity": a.get("activity_level"),
                "stance": a.get("stance"),
            }
            for a in sim_cfg.get("agent_configs", [])
        ]

        # Reports for this simulation
        reports_detail = []
        for rep in sim_entry["report_ids"]:
            report_id = rep["report_id"]
            meta_path = os.path.join(rep["report_dir"], "meta.json")
            outline_path = os.path.join(rep["report_dir"], "outline.json")

            report_meta = {}
            if os.path.isfile(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        report_meta = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass

            outline = {}
            if os.path.isfile(outline_path):
                try:
                    with open(outline_path, "r", encoding="utf-8") as f:
                        outline = json.load(f)
                except (OSError, json.JSONDecodeError):
                    pass

            # Extract section titles only — skip full section content (too large)
            section_titles = [
                s.get("title", "") for s in outline.get("sections", [])
            ]

            reports_detail.append({
                "report_id": report_id,
                "status": report_meta.get("status"),
                "created_at": report_meta.get("created_at"),
                "completed_at": report_meta.get("completed_at"),
                "title": outline.get("title"),
                "summary": outline.get("summary"),
                "section_titles": section_titles,
            })

        simulations_detail.append({
            "simulation_id": sim_id,
            "status": sim_status.get("status", "unknown"),
            "total_rounds": total_rounds,
            "llm_model": sim_cfg.get("llm_model"),
            "llm_base_url": sim_cfg.get("llm_base_url"),
            "simulation_requirement": sim_cfg.get("simulation_requirement"),
            "agent_count": len(agents),
            "agents": agents,
            "turning_points": turning_points,
            "reports": reports_detail,
        })

    # ── Project summary ───────────────────────────────────────────────────
    icp_file = project.files[0].get("original_filename", "") if project.files else ""

    detail = {
        "project": {
            "project_id": project_id,
            "name": project.name,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "status": project.status.value if hasattr(project.status, "value") else project.status,
            "graph_id": graph_id,
            "icp_file": icp_file,
            "simulation_requirement": project.simulation_requirement,
        },
        "graph": graph_summary,
        "simulations": simulations_detail,
    }

    logger.info("Run detail fetched for project %s", project_id)
    return jsonify({"success": True, "data": detail})


@runs_bp.route("/<project_id>", methods=["DELETE"])
def delete_run(project_id: str):
    """
    DELETE /api/runs/<project_id> — remove every artifact for one run.

    Deletion order (safe even if intermediate steps fail partially):
      1. Find simulations + reports for this project
      2. Delete Neo4j graph (requires backend connection)
      3. Delete report directories
      4. Delete simulation directories
      5. Delete project directory

    Returns a summary of what was deleted.
    """
    project = ProjectManager.get_project(project_id)
    if project is None:
        logger.warning("delete_run: project not found — %s", project_id)
        return jsonify({"success": False, "error": f"Project {project_id} not found"}), 404

    graph_id = project.graph_id
    simulations = _simulations_for_project(project_id)

    # Tally for the response summary
    deleted_simulations = 0
    deleted_reports = 0
    graph_deleted = False

    # 1. Delete Neo4j graph — requires a live backend connection.
    storage = current_app.extensions.get("neo4j_storage")
    if graph_id and storage:
        try:
            storage.delete_graph(graph_id)
            graph_deleted = True
            logger.info("Deleted Neo4j graph %s (project %s)", graph_id, project_id)
        except Exception as exc:
            # Log but continue — we still want the file artifacts cleaned up.
            logger.error(
                "Failed to delete Neo4j graph %s: %s — continuing with file cleanup",
                graph_id, exc,
            )
    elif graph_id and not storage:
        logger.warning("Neo4j storage unavailable — graph %s not deleted", graph_id)

    # 2. Delete report directories
    for sim in simulations:
        for rep in sim["report_ids"]:
            try:
                shutil.rmtree(rep["report_dir"], ignore_errors=True)
                deleted_reports += 1
                logger.debug("Deleted report dir %s", rep["report_dir"])
            except Exception as exc:
                logger.error("Error deleting report %s: %s", rep["report_id"], exc)

    # 3. Delete simulation directories
    for sim in simulations:
        try:
            shutil.rmtree(sim["sim_dir"], ignore_errors=True)
            deleted_simulations += 1
            logger.debug("Deleted simulation dir %s", sim["sim_dir"])
        except Exception as exc:
            logger.error("Error deleting simulation %s: %s", sim["simulation_id"], exc)

    # 4. Delete project directory (ProjectManager.delete_project wraps shutil.rmtree)
    ProjectManager.delete_project(project_id)
    logger.info(
        "Deleted run %s — sims: %d, reports: %d, graph: %s",
        project_id, deleted_simulations, deleted_reports, graph_deleted,
    )

    return jsonify({
        "success": True,
        "data": {
            "project_id": project_id,
            "deleted_simulations": deleted_simulations,
            "deleted_reports": deleted_reports,
            "graph_deleted": graph_deleted,
        },
    })
