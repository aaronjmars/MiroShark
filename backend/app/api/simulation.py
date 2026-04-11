"""
Simulation-related API routes
Step 2: Entity reading and filtering, OASIS simulation preparation and execution (fully automated)
"""

import os
import io
import csv
import json
import traceback
import tempfile
from datetime import datetime
from flask import request, jsonify, send_file, current_app

from . import simulation_bp
from ..config import Config
from ..services.entity_reader import EntityReader
from ..services.oasis_profile_generator import OasisProfileGenerator
from ..services.simulation_manager import SimulationManager, SimulationStatus
from ..services.simulation_config_generator import SimulationConfigGenerator
from ..services.simulation_runner import SimulationRunner, RunnerStatus
from ..utils.logger import get_logger
from ..models.project import ProjectManager

logger = get_logger('miroshark.api.simulation')


# Interview prompt optimization prefix
# Adding this prefix prevents Agents from calling tools and makes them reply with text directly
INTERVIEW_PROMPT_PREFIX = "Based on your persona, all past memories and actions, reply directly with text without calling any tools: "


def _ensure_env_alive(simulation_id: str) -> bool:
    """
    Check if simulation environment is alive. If not, try to restart it
    in env-only mode for interviews. Returns True if env is alive.
    """
    if SimulationRunner.check_env_alive(simulation_id):
        return True

    # Try to auto-restart the environment
    logger.info(f"Environment not alive for {simulation_id}, attempting auto-restart for interviews...")
    is_prepared, _ = _check_simulation_prepared(simulation_id)
    if not is_prepared:
        return False

    try:
        SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform='parallel',
            start_round=0,
            env_only=True
        )
        # Wait a bit for the env to start
        import time
        for _ in range(15):
            time.sleep(2)
            if SimulationRunner.check_env_alive(simulation_id):
                logger.info(f"Environment auto-restarted for {simulation_id}")
                return True
        logger.warning(f"Environment auto-restart timed out for {simulation_id}")
        return False
    except Exception as e:
        logger.error(f"Failed to auto-restart environment: {e}")
        return False


def optimize_interview_prompt(prompt: str) -> str:
    """
    Optimize interview prompt by adding prefix to prevent Agent from calling tools

    Args:
        prompt: Original question

    Returns:
        Optimized question
    """
    if not prompt:
        return prompt
    # Avoid adding prefix repeatedly
    if prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{prompt}"


# ============== Entity Reading Endpoints ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    Get all entities from the graph (filtered)

    Only returns nodes matching predefined entity types (nodes whose Labels are not just Entity)

    Query parameters:
        entity_types: Comma-separated list of entity types (optional, for further filtering)
        enrich: Whether to include related edge information (default true)
    """
    try:
        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        logger.info(f"Fetching graph entities: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to fetch graph entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Get detailed information for a single entity"""
    try:
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        entity = reader.get_entity_with_context(graph_id, entity_uuid)
        
        if not entity:
            return jsonify({
                "success": False,
                "error": f"Entity not found: {entity_uuid}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get entity details: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get all entities of a specified type"""
    try:
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        entities = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "count": len(entities),
                "entities": [e.to_dict() for e in entities]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get entities: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Management Endpoints ==============

@simulation_bp.route('/create', methods=['POST'])
def create_simulation():
    """
    Create a new simulation

    Note: Parameters like max_rounds are intelligently generated by LLM, no manual setup needed

    Request (JSON):
        {
            "project_id": "proj_xxxx",      // Required
            "graph_id": "miroshark_xxxx",    // Optional, fetched from project if not provided
            "enable_twitter": true,          // Optional, default true
            "enable_reddit": true,           // Optional, default true
            "enable_polymarket": false       // Optional, default false
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "project_id": "proj_xxxx",
                "graph_id": "miroshark_xxxx",
                "status": "created",
                "enable_twitter": true,
                "enable_reddit": true,
                "created_at": "2025-12-01T10:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        if not project_id:
            return jsonify({
                "success": False,
                "error": "Please provide project_id"
            }), 400
        
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project not found: {project_id}"
            }), 404
        
        graph_id = data.get('graph_id') or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Graph not yet built for this project, please call /api/graph/build first"
            }), 400
        
        manager = SimulationManager()
        state = manager.create_simulation(
            project_id=project_id,
            graph_id=graph_id,
            enable_twitter=data.get('enable_twitter', True),
            enable_reddit=data.get('enable_reddit', True),
            enable_polymarket=data.get('enable_polymarket', False),
        )
        
        return jsonify({
            "success": True,
            "data": state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to create simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/fork', methods=['POST'])
def fork_simulation():
    """
    Fork an existing simulation into a new child simulation.

    Copies agent profiles and configuration from the parent so the child
    is immediately ready to run.  Optionally accepts a new
    simulation_requirement to explore a different scenario with the same
    agent population.

    Request (JSON):
        {
            "parent_simulation_id": "sim_xxxx",        // Required
            "simulation_requirement": "What if..."     // Optional override
        }

    Returns:
        {
            "success": true,
            "data": { ...simulation state... }
        }
    """
    try:
        data = request.get_json() or {}

        parent_simulation_id = data.get('parent_simulation_id')
        if not parent_simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide parent_simulation_id"
            }), 400

        simulation_requirement = data.get('simulation_requirement') or None

        manager = SimulationManager()
        state = manager.fork_simulation(
            parent_simulation_id=parent_simulation_id,
            simulation_requirement=simulation_requirement,
        )

        return jsonify({
            "success": True,
            "data": state.to_dict()
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404

    except Exception as e:
        logger.error(f"Failed to fork simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _check_simulation_prepared(simulation_id: str) -> tuple:
    """
    Check if the simulation has been prepared

    Conditions checked:
    1. state.json exists and status is "ready"
    2. Required files exist: reddit_profiles.json, twitter_profiles.csv, simulation_config.json

    Note: Run scripts (run_*.py) remain in backend/scripts/ directory and are no longer copied to simulation directory

    Args:
        simulation_id: Simulation ID

    Returns:
        (is_prepared: bool, info: dict)
    """
    import os
    from ..config import Config
    
    simulation_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    
    # Check if directory exists
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulation directory does not exist"}
    
    # Required files list (excluding scripts, which are in backend/scripts/)
    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv"
    ]
    
    # Check if files exist
    existing_files = []
    missing_files = []
    for f in required_files:
        file_path = os.path.join(simulation_dir, f)
        if os.path.exists(file_path):
            existing_files.append(f)
        else:
            missing_files.append(f)
    
    if missing_files:
        return False, {
            "reason": "Missing required files",
            "missing_files": missing_files,
            "existing_files": existing_files
        }
    
    # Check status in state.json
    state_file = os.path.join(simulation_dir, "state.json")
    try:
        import json
        with open(state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        
        # Detailed logging
        logger.debug(f"Checking simulation preparation status: {simulation_id}, status={status}, config_generated={config_generated}")
        
        # If config_generated=True and files exist, consider preparation complete
        # The following statuses indicate preparation is complete:
        # - ready: preparation complete, can run
        # - preparing: if config_generated=True it means completed
        # - running: currently running, preparation was done long ago
        # - completed: run finished, preparation was done long ago
        # - stopped: stopped, preparation was done long ago
        # - failed: run failed (but preparation is complete)
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed", "paused"]
        if status in prepared_statuses and config_generated:
            # Get file statistics
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            config_file = os.path.join(simulation_dir, "simulation_config.json")
            
            profiles_count = 0
            if os.path.exists(profiles_file):
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    profiles_data = json.load(f)
                    profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0
            
            # If status is preparing but files are complete, auto-update status to ready
            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    from datetime import datetime
                    state_data["updated_at"] = datetime.now().isoformat()
                    with open(state_file, 'w', encoding='utf-8') as f:
                        json.dump(state_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"Auto-updated simulation status: {simulation_id} preparing -> ready")
                    status = "ready"
                except Exception as e:
                    logger.warning(f"Failed to auto-update status: {e}")
            
            logger.info(f"Simulation {simulation_id} check result: preparation complete (status={status}, config_generated={config_generated})")
            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files
            }
        else:
            logger.warning(f"Simulation {simulation_id} check result: not prepared (status={status}, config_generated={config_generated})")
            return False, {
                "reason": f"Status not in prepared list or config_generated is false: status={status}, config_generated={config_generated}",
                "status": status,
                "config_generated": config_generated
            }
            
    except Exception as e:
        return False, {"reason": f"Failed to read state file: {str(e)}"}


@simulation_bp.route('/prepare', methods=['POST'])
def prepare_simulation():
    """
    Prepare simulation environment (async task, LLM intelligently generates all parameters)

    This is a time-consuming operation. The endpoint returns task_id immediately.
    Use GET /api/simulation/prepare/status to query progress.

    Features:
    - Auto-detects completed preparation work to avoid redundant generation
    - If already prepared, returns existing results directly
    - Supports forced regeneration (force_regenerate=true)

    Steps:
    1. Check if preparation work has already been completed
    2. Read and filter entities from knowledge graph
    3. Generate OASIS Agent Profile for each entity (with retry mechanism)
    4. LLM intelligently generates simulation configuration (with retry mechanism)
    5. Save configuration files and preset scripts

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                   // Required, simulation ID
            "entity_types": ["Student", "PublicFigure"],  // Optional, specify entity types
            "use_llm_for_profiles": true,                 // Optional, whether to use LLM for profile generation
            "parallel_profile_count": 5,                  // Optional, parallel profile generation count, default 5
            "force_regenerate": false                     // Optional, force regeneration, default false
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",           // Returned for new tasks
                "status": "preparing|ready",
                "message": "Preparation task started | Preparation already complete",
                "already_prepared": true|false    // Whether preparation is complete
            }
        }
    """
    import threading
    import os
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config
    
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404
        
        # Check if force regeneration is requested
        force_regenerate = data.get('force_regenerate', False)
        logger.info(f"Processing /prepare request: simulation_id={simulation_id}, force_regenerate={force_regenerate}")
        
        # Check if already prepared (avoid redundant generation)
        if not force_regenerate:
            logger.debug(f"Checking if simulation {simulation_id} is already prepared...")
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            logger.debug(f"Check result: is_prepared={is_prepared}, prepare_info={prepare_info}")
            if is_prepared:
                logger.info(f"Simulation {simulation_id} already prepared, skipping redundant generation")
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "message": "Preparation already complete, no need to regenerate",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
            else:
                logger.info(f"Simulation {simulation_id} not yet prepared, starting preparation task")
        
        # Get required information from project
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"Project not found: {state.project_id}"
            }), 404
        
        # Get simulation requirement
        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Project missing simulation requirement description (simulation_requirement)"
            }), 400
        
        # Get document text
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        
        entity_types_list = data.get('entity_types')
        use_llm_for_profiles = data.get('use_llm_for_profiles', True)
        parallel_profile_count = data.get('parallel_profile_count', 5)
        
        # ========== Get GraphStorage (capture reference before background task starts) ==========
        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized — check Neo4j connection")

        # ========== Synchronously get entity count (before background task starts) ==========
        # This allows the frontend to get the expected total Agent count immediately after calling prepare
        try:
            logger.info(f"Synchronously fetching entity count: graph_id={state.graph_id}")
            reader = EntityReader(storage)
            # Quick entity read (no edge info needed, just counting)
            filtered_preview = reader.filter_defined_entities(
                graph_id=state.graph_id,
                defined_entity_types=entity_types_list,
                enrich_with_edges=False  # Skip edge info for faster processing
            )
            # Save entity count to state (for frontend to fetch immediately)
            state.entities_count = filtered_preview.filtered_count
            state.entity_types = list(filtered_preview.entity_types)
            logger.info(f"Expected entity count: {filtered_preview.filtered_count}, types: {filtered_preview.entity_types}")
        except Exception as e:
            logger.warning(f"Failed to synchronously get entity count (will retry in background task): {e}")
            # Failure does not affect subsequent flow, background task will re-fetch
        
        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_prepare",
            metadata={
                "simulation_id": simulation_id,
                "project_id": state.project_id
            }
        )
        
        # Update simulation state (includes pre-fetched entity count)
        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)
        
        # Define background task
        def run_prepare():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Starting simulation environment preparation..."
                )
                
                # Prepare simulation (with progress callback)
                # Store stage progress details
                stage_details = {}
                
                def progress_callback(stage, progress, message, **kwargs):
                    # Calculate overall progress
                    stage_weights = {
                        "reading": (0, 20),           # 0-20%
                        "generating_profiles": (20, 70),  # 20-70%
                        "generating_config": (70, 90),    # 70-90%
                        "copying_scripts": (90, 100)       # 90-100%
                    }
                    
                    start, end = stage_weights.get(stage, (0, 100))
                    current_progress = int(start + (end - start) * progress / 100)
                    
                    # Build detailed progress info
                    stage_names = {
                        "reading": "Reading graph entities",
                        "generating_profiles": "Generating Agent profiles",
                        "generating_config": "Generating simulation config",
                        "copying_scripts": "Preparing simulation scripts"
                    }
                    
                    stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
                    total_stages = len(stage_weights)
                    
                    # Update stage details
                    stage_details[stage] = {
                        "stage_name": stage_names.get(stage, stage),
                        "stage_progress": progress,
                        "current": kwargs.get("current", 0),
                        "total": kwargs.get("total", 0),
                        "item_name": kwargs.get("item_name", "")
                    }
                    
                    # Build detailed progress info
                    detail = stage_details[stage]
                    progress_detail_data = {
                        "current_stage": stage,
                        "current_stage_name": stage_names.get(stage, stage),
                        "stage_index": stage_index,
                        "total_stages": total_stages,
                        "stage_progress": progress,
                        "current_item": detail["current"],
                        "total_items": detail["total"],
                        "item_description": message
                    }
                    
                    # Build concise message
                    if detail["total"] > 0:
                        detailed_message = (
                            f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                            f"{detail['current']}/{detail['total']} - {message}"
                        )
                    else:
                        detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
                    
                    task_manager.update_task(
                        task_id,
                        progress=current_progress,
                        message=detailed_message,
                        progress_detail=progress_detail_data
                    )
                
                result_state = manager.prepare_simulation(
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    defined_entity_types=entity_types_list,
                    use_llm_for_profiles=use_llm_for_profiles,
                    progress_callback=progress_callback,
                    parallel_profile_count=parallel_profile_count,
                    storage=storage
                )
                
                # Task complete
                task_manager.complete_task(
                    task_id,
                    result=result_state.to_simple_dict()
                )
                
            except Exception as e:
                logger.error(f"Failed to prepare simulation: {str(e)}")
                task_manager.fail_task(task_id, str(e))
                
                # Update simulation status to failed
                state = manager.get_simulation(simulation_id)
                if state:
                    state.status = SimulationStatus.FAILED
                    state.error = str(e)
                    manager._save_simulation_state(state)
        
        # Start background thread
        thread = threading.Thread(target=run_prepare, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "Preparation task started, query progress via /api/simulation/prepare/status",
                "already_prepared": False,
                "expected_entities_count": state.entities_count,  # Expected total Agent count
                "entity_types": state.entity_types  # Entity type list
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to start preparation task: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/prepare/status', methods=['POST'])
def get_prepare_status():
    """
    Query preparation task progress

    Supports two query methods:
    1. Query ongoing task progress by task_id
    2. Check if preparation is already complete by simulation_id

    Request (JSON):
        {
            "task_id": "task_xxxx",          // Optional, task_id returned from prepare
            "simulation_id": "sim_xxxx"      // Optional, simulation ID (to check completed preparation)
        }

    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|ready",
                "progress": 45,
                "message": "...",
                "already_prepared": true|false,  // Whether preparation is already complete
                "prepare_info": {...}            // Detailed info when preparation is complete
            }
        }
    """
    from ..models.task import TaskManager
    
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        
        # If simulation_id is provided, first check if preparation is complete
        if simulation_id:
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
            if is_prepared:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "ready",
                        "progress": 100,
                        "message": "Preparation work already complete",
                        "already_prepared": True,
                        "prepare_info": prepare_info
                    }
                })
        
        # If no task_id, return error
        if not task_id:
            if simulation_id:
                # Has simulation_id but not yet prepared
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "status": "not_started",
                        "progress": 0,
                        "message": "Preparation not yet started, call /api/simulation/prepare to begin",
                        "already_prepared": False
                    }
                })
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            # Task not found, but if simulation_id is provided, check if preparation is complete
            if simulation_id:
                is_prepared, prepare_info = _check_simulation_prepared(simulation_id)
                if is_prepared:
                    return jsonify({
                        "success": True,
                        "data": {
                            "simulation_id": simulation_id,
                            "task_id": task_id,
                            "status": "ready",
                            "progress": 100,
                            "message": "Task completed (preparation already exists)",
                            "already_prepared": True,
                            "prepare_info": prepare_info
                        }
                    })
            
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_id}"
            }), 404
        
        task_dict = task.to_dict()
        task_dict["already_prepared"] = False
        
        return jsonify({
            "success": True,
            "data": task_dict
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@simulation_bp.route('/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """Get simulation status"""
    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        
        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404
        
        result = state.to_dict()
        
        # If simulation is ready, append run instructions
        if state.status == SimulationStatus.READY:
            result["run_instructions"] = manager.get_run_instructions(simulation_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/list', methods=['GET'])
def list_simulations():
    """
    List all simulations

    Query parameters:
        project_id: Filter by project ID (optional)
    """
    try:
        project_id = request.args.get('project_id')
        
        manager = SimulationManager()
        simulations = manager.list_simulations(project_id=project_id)
        
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in simulations],
            "count": len(simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to list simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


def _get_report_id_for_simulation(simulation_id: str) -> str:
    """
    Get the latest report_id corresponding to a simulation

    Traverses the reports directory to find reports matching the simulation_id.
    If multiple exist, returns the most recent one (sorted by created_at).

    Args:
        simulation_id: Simulation ID

    Returns:
        report_id or None
    """
    import json
    from datetime import datetime
    
    # reports directory path: backend/uploads/reports
    # __file__ is app/api/simulation.py, need to go up two levels to backend/
    reports_dir = os.path.join(os.path.dirname(__file__), '../../uploads/reports')
    if not os.path.exists(reports_dir):
        return None
    
    matching_reports = []
    
    try:
        for report_folder in os.listdir(reports_dir):
            report_path = os.path.join(reports_dir, report_folder)
            if not os.path.isdir(report_path):
                continue
            
            meta_file = os.path.join(report_path, "meta.json")
            if not os.path.exists(meta_file):
                continue
            
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
                
                if meta.get("simulation_id") == simulation_id:
                    matching_reports.append({
                        "report_id": meta.get("report_id"),
                        "created_at": meta.get("created_at", ""),
                        "status": meta.get("status", "")
                    })
            except Exception:
                continue
        
        if not matching_reports:
            return None
        
        # Sort by creation time descending, return the most recent
        matching_reports.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return matching_reports[0].get("report_id")
        
    except Exception as e:
        logger.warning(f"Failed to find report for simulation {simulation_id}: {e}")
        return None


@simulation_bp.route('/history', methods=['GET'])
def get_simulation_history():
    """
    Get historical simulation list (with project details)

    Used for homepage historical project display, returns simulation list with rich information including project name, description, etc.

    Query parameters:
        limit: Return count limit (default 20)

    Returns:
        {
            "success": true,
            "data": [
                {
                    "simulation_id": "sim_xxxx",
                    "project_id": "proj_xxxx",
                    "project_name": "WHU Public Opinion Analysis",
                    "simulation_requirement": "If Wuhan University publishes...",
                    "status": "completed",
                    "entities_count": 68,
                    "profiles_count": 68,
                    "entity_types": ["Student", "Professor", ...],
                    "created_at": "2024-12-10",
                    "updated_at": "2024-12-10",
                    "total_rounds": 120,
                    "current_round": 120,
                    "report_id": "report_xxxx",
                    "version": "v1.0.2"
                },
                ...
            ],
            "count": 7
        }
    """
    try:
        limit = request.args.get('limit', 20, type=int)
        
        manager = SimulationManager()
        simulations = manager.list_simulations()[:limit]
        
        # Enrich simulation data, read only from Simulation files
        enriched_simulations = []
        for sim in simulations:
            sim_dict = sim.to_dict()
            
            # Get simulation config info (read simulation_requirement from simulation_config.json)
            config = manager.get_simulation_config(sim.simulation_id)
            if config:
                sim_dict["simulation_requirement"] = config.get("simulation_requirement", "")
                time_config = config.get("time_config", {})
                sim_dict["total_simulation_hours"] = time_config.get("total_simulation_hours", 0)
                # Recommended rounds (fallback value)
                recommended_rounds = int(
                    time_config.get("total_simulation_hours", 0) * 60 / 
                    max(time_config.get("minutes_per_round", 60), 1)
                )
            else:
                sim_dict["simulation_requirement"] = ""
                sim_dict["total_simulation_hours"] = 0
                recommended_rounds = 0
            
            # Get run status (read user-set actual rounds from run_state.json)
            run_state = SimulationRunner.get_run_state(sim.simulation_id)
            if run_state:
                sim_dict["current_round"] = run_state.current_round
                sim_dict["runner_status"] = run_state.runner_status.value
                # Use user-set total_rounds, fall back to recommended rounds
                sim_dict["total_rounds"] = run_state.total_rounds if run_state.total_rounds > 0 else recommended_rounds
            else:
                sim_dict["current_round"] = 0
                sim_dict["runner_status"] = "idle"
                sim_dict["total_rounds"] = recommended_rounds
            
            # Get associated project file list (max 3)
            project = ProjectManager.get_project(sim.project_id)
            if project and hasattr(project, 'files') and project.files:
                sim_dict["files"] = [
                    {"filename": f.get("filename", "Unknown file")} 
                    for f in project.files[:3]
                ]
            else:
                sim_dict["files"] = []
            
            # Get associated report_id (find the latest report for this simulation)
            sim_dict["report_id"] = _get_report_id_for_simulation(sim.simulation_id)
            
            # Propagate fork lineage fields (already in to_dict but ensure they surface)
            sim_dict.setdefault("parent_simulation_id", sim.parent_simulation_id)

            # Add version number
            sim_dict["version"] = "v1.0.2"
            
            # Format date
            try:
                created_date = sim_dict.get("created_at", "")[:10]
                sim_dict["created_date"] = created_date
            except:
                sim_dict["created_date"] = ""
            
            enriched_simulations.append(sim_dict)
        
        return jsonify({
            "success": True,
            "data": enriched_simulations,
            "count": len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Failed to get simulation history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles', methods=['GET'])
def get_simulation_profiles(simulation_id: str):
    """
    Get simulation Agent Profiles

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        
        manager = SimulationManager()
        profiles = manager.get_profiles(simulation_id, platform=platform)
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "count": len(profiles),
                "profiles": profiles
            }
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 404
        
    except Exception as e:
        logger.error(f"Failed to get profiles: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/profiles/realtime', methods=['GET'])
def get_simulation_profiles_realtime(simulation_id: str):
    """
    Get simulation Agent Profiles in real-time (for viewing progress during generation)

    Differences from /profiles endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during generation
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)

    Query parameters:
        platform: Platform type (reddit/twitter, default reddit)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "platform": "reddit",
                "count": 15,
                "total_expected": 93,  // Expected total (if available)
                "is_generating": true,  // Whether generation is in progress
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "profiles": [...]
            }
        }
    """
    import json
    import csv
    from datetime import datetime
    
    try:
        platform = request.args.get('platform', 'reddit')
        
        # Get simulation directory
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # Determine file path
        if platform == "reddit":
            profiles_file = os.path.join(sim_dir, "reddit_profiles.json")
        else:
            profiles_file = os.path.join(sim_dir, "twitter_profiles.csv")

        # Check if file exists
        file_exists = os.path.exists(profiles_file)
        profiles = []
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(profiles_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                if platform == "reddit":
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                else:
                    with open(profiles_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        profiles = list(reader)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read profiles file (may be in the process of writing): {e}")
                profiles = []
        
        # Check if generation is in progress (determined by state.json)
        is_generating = False
        total_expected = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    status = state_data.get("status", "")
                    is_generating = status == "preparing"
                    total_expected = state_data.get("entities_count")
            except Exception:
                pass
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "platform": platform,
                "count": len(profiles),
                "total_expected": total_expected,
                "is_generating": is_generating,
                "file_exists": file_exists,
                "file_modified_at": file_modified_at,
                "profiles": profiles
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get profiles in real-time: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/realtime', methods=['GET'])
def get_simulation_config_realtime(simulation_id: str):
    """
    Get simulation configuration in real-time (for viewing progress during generation)

    Differences from /config endpoint:
    - Reads files directly, bypassing SimulationManager
    - Suitable for real-time viewing during generation
    - Returns additional metadata (e.g., file modification time, whether generation is in progress)
    - Can return partial info even if config generation is not yet complete

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "file_exists": true,
                "file_modified_at": "2025-12-04T18:20:00",
                "is_generating": true,  // Whether generation is in progress
                "generation_stage": "generating_config",  // Current generation stage
                "config": {...}  // Config content (if available)
            }
        }
    """
    import json
    from datetime import datetime
    
    try:
        # Get simulation directory
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)

        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # Config file path
        config_file = os.path.join(sim_dir, "simulation_config.json")
        
        # Check if file exists
        file_exists = os.path.exists(config_file)
        config = None
        file_modified_at = None
        
        if file_exists:
            # Get file modification time
            file_stat = os.stat(config_file)
            file_modified_at = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Failed to read config file (may be in the process of writing): {e}")
                config = None
        
        # Check if generation is in progress (determined by state.json)
        is_generating = False
        generation_stage = None
        config_generated = False
        sim_status = ""
        config_error = None

        state_file = os.path.join(sim_dir, "state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    sim_status = state_data.get("status", "")
                    is_generating = sim_status == "preparing"
                    config_generated = state_data.get("config_generated", False)

                    # Expose error when generation failed
                    if sim_status == "failed":
                        config_error = state_data.get("error") or "Config generation failed"

                    # Determine current stage
                    if is_generating:
                        if state_data.get("profiles_generated", False):
                            generation_stage = "generating_config"
                        else:
                            generation_stage = "generating_profiles"
                    elif sim_status == "ready":
                        generation_stage = "completed"
            except Exception:
                pass

        # Build response data
        response_data = {
            "simulation_id": simulation_id,
            "file_exists": file_exists,
            "file_modified_at": file_modified_at,
            "is_generating": is_generating,
            "generation_stage": generation_stage,
            "config_generated": config_generated,
            "status": sim_status,
            "config_error": config_error,
            "config": config
        }
        
        # If config exists, extract some key statistics
        if config:
            response_data["summary"] = {
                "total_agents": len(config.get("agent_configs", [])),
                "simulation_hours": config.get("time_config", {}).get("total_simulation_hours"),
                "initial_posts_count": len(config.get("event_config", {}).get("initial_posts", [])),
                "hot_topics_count": len(config.get("event_config", {}).get("hot_topics", [])),
                "has_twitter_config": "twitter_config" in config,
                "has_reddit_config": "reddit_config" in config,
                "generated_at": config.get("generated_at"),
                "llm_model": config.get("llm_model")
            }
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get config in real-time: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/retry', methods=['POST'])
def retry_simulation_config(simulation_id: str):
    """
    Retry config generation only (profiles already exist).

    Resets the simulation status to 'preparing', then regenerates the
    simulation_config.json from existing profiles and entities without
    repeating the (slow) profile generation step.

    Returns:
        { "success": true, "data": { "simulation_id": "...", "status": "preparing" } }
    """
    import threading
    from ..models.task import TaskManager, TaskStatus
    from ..config import Config

    try:
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if not state:
            return jsonify({"success": False, "error": f"Simulation not found: {simulation_id}"}), 404

        # Profiles must exist before we can retry config generation
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        profiles_exist = (
            os.path.exists(os.path.join(sim_dir, "reddit_profiles.json")) or
            os.path.exists(os.path.join(sim_dir, "twitter_profiles.csv"))
        )
        if not profiles_exist:
            return jsonify({
                "success": False,
                "error": "Agent profiles not found — run /prepare first"
            }), 400

        # Get project data needed for config generation
        project = ProjectManager.get_project(state.project_id)
        if not project:
            return jsonify({"success": False, "error": f"Project not found: {state.project_id}"}), 404

        simulation_requirement = project.simulation_requirement or ""
        document_text = ProjectManager.get_extracted_text(state.project_id) or ""

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            return jsonify({"success": False, "error": "GraphStorage not initialized"}), 500

        # Reset state so the frontend polling loop sees "preparing" again
        state.status = SimulationStatus.PREPARING
        state.config_generated = False
        state.error = None
        manager._save_simulation_state(state)

        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="simulation_config_retry",
            metadata={"simulation_id": simulation_id}
        )

        def run_config_retry():
            try:
                task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=0,
                                         message="Retrying config generation...")

                # Re-read entities for config generation context
                reader = EntityReader(storage)
                filtered = reader.filter_defined_entities(
                    graph_id=state.graph_id,
                    enrich_with_edges=True
                )

                config_generator = SimulationConfigGenerator()
                sim_params = config_generator.generate_config(
                    simulation_id=simulation_id,
                    project_id=state.project_id,
                    graph_id=state.graph_id,
                    simulation_requirement=simulation_requirement,
                    document_text=document_text,
                    entities=filtered.entities,
                    enable_twitter=state.enable_twitter,
                    enable_reddit=state.enable_reddit,
                )

                config_path = os.path.join(sim_dir, "simulation_config.json")
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(sim_params.to_json())

                # Mark as complete
                reload_state = manager.get_simulation(simulation_id)
                if reload_state:
                    reload_state.config_generated = True
                    reload_state.config_reasoning = sim_params.generation_reasoning
                    reload_state.status = SimulationStatus.READY
                    reload_state.error = None
                    manager._save_simulation_state(reload_state)

                task_manager.complete_task(task_id, result={"simulation_id": simulation_id})
                logger.info(f"Config retry complete for {simulation_id}")

            except Exception as e:
                logger.error(f"Config retry failed for {simulation_id}: {e}")
                task_manager.fail_task(task_id, str(e))
                failed_state = manager.get_simulation(simulation_id)
                if failed_state:
                    failed_state.status = SimulationStatus.FAILED
                    failed_state.error = str(e)
                    manager._save_simulation_state(failed_state)

        thread = threading.Thread(target=run_config_retry, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "task_id": task_id,
                "status": "preparing",
                "message": "Config generation retry started"
            }
        })

    except Exception as e:
        logger.error(f"Failed to start config retry: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@simulation_bp.route('/<simulation_id>/config', methods=['GET'])
def get_simulation_config(simulation_id: str):
    """
    Get simulation configuration (complete configuration intelligently generated by LLM)

    Returns containing:
        - time_config: Time configuration (simulation duration, rounds, peak/off-peak hours)
        - agent_configs: Activity configuration for each agent (activity level, posting frequency, stance, etc.)
        - event_config: Event configuration (initial posts, hot topics)
        - platform_configs: Platform configuration
        - generation_reasoning: LLM configuration reasoning explanation
    """
    try:
        manager = SimulationManager()
        config = manager.get_simulation_config(simulation_id)
        
        if not config:
            return jsonify({
                "success": False,
                "error": "Simulation configuration does not exist, please call /prepare endpoint first"
            }), 404
        
        return jsonify({
            "success": True,
            "data": config
        })
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/config/download', methods=['GET'])
def download_simulation_config(simulation_id: str):
    """Download simulation configuration file"""
    try:
        manager = SimulationManager()
        sim_dir = manager._get_simulation_dir(simulation_id)
        config_path = os.path.join(sim_dir, "simulation_config.json")
        
        if not os.path.exists(config_path):
            return jsonify({
                "success": False,
                "error": "Configuration file does not exist, please call /prepare endpoint first"
            }), 404
        
        return send_file(
            config_path,
            as_attachment=True,
            download_name="simulation_config.json"
        )
        
    except Exception as e:
        logger.error(f"Failed to download configuration: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/script/<script_name>/download', methods=['GET'])
def download_simulation_script(script_name: str):
    """
    Download simulation run script file (common scripts, located at backend/scripts/)

    Options for script_name:
        - run_twitter_simulation.py
        - run_reddit_simulation.py
        - run_parallel_simulation.py
        - action_logger.py
    """
    try:
        # Scripts located at backend/scripts/ directory
        scripts_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
        
        # Validate script name
        allowed_scripts = [
            "run_twitter_simulation.py",
            "run_reddit_simulation.py", 
            "run_parallel_simulation.py",
            "action_logger.py"
        ]
        
        if script_name not in allowed_scripts:
            return jsonify({
                "success": False,
                "error": f"Unknown script: {script_name}, options: {allowed_scripts}"
            }), 400
        
        script_path = os.path.join(scripts_dir, script_name)
        
        if not os.path.exists(script_path):
            return jsonify({
                "success": False,
                "error": f"Script file does not exist: {script_name}"
            }), 404
        
        return send_file(
            script_path,
            as_attachment=True,
            download_name=script_name
        )
        
    except Exception as e:
        logger.error(f"Failed to download script: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Profile Generation Endpoint (standalone use) ==============

@simulation_bp.route('/generate-profiles', methods=['POST'])
def generate_profiles():
    """
    Directly generate OASIS Agent Profile from graph (without creating simulation)

    Request (JSON):
        {
            "graph_id": "miroshark_xxxx",     // Required
            "entity_types": ["Student"],      // Optional
            "use_llm": true,                  // Optional
            "platform": "reddit"              // Optional
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id"
            }), 400
        
        entity_types = data.get('entity_types')
        use_llm = data.get('use_llm', True)
        platform = data.get('platform', 'reddit')

        storage = current_app.extensions.get('neo4j_storage')
        if not storage:
            raise ValueError("GraphStorage not initialized")
        reader = EntityReader(storage)
        filtered = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=True
        )
        
        if filtered.filtered_count == 0:
            return jsonify({
                "success": False,
                "error": "No matching entities found"
            }), 400
        
        generator = OasisProfileGenerator()
        profiles = generator.generate_profiles_from_entities(
            entities=filtered.entities,
            use_llm=use_llm
        )
        
        if platform == "reddit":
            profiles_data = [p.to_reddit_format() for p in profiles]
        elif platform == "twitter":
            profiles_data = [p.to_twitter_format() for p in profiles]
        else:
            profiles_data = [p.to_dict() for p in profiles]
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "entity_types": list(filtered.entity_types),
                "count": len(profiles_data),
                "profiles": profiles_data
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to generate profile: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Run Control Endpoints ==============

@simulation_bp.route('/start', methods=['POST'])
def start_simulation():
    """
    Start running simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",          // Required, simulation ID
            "platform": "parallel",                // Optional: twitter / reddit / parallel (default)
            "max_rounds": 100,                     // Optional: maximum simulation rounds, used to truncate overly long simulations
            "enable_graph_memory_update": false,   // Optional: whether to dynamically update agent activity to knowledge graph memory
            "force": false                         // Optional: force restart (will stop running simulation and clean up logs)
        }

    About the force parameter:
        - When enabled, if simulation is running or completed, it will first stop and clean up run logs
        - Cleanup includes: run_state.json, actions.jsonl, simulation.log, etc.
        - Will not clean up configuration files (simulation_config.json) and profile files
        - Suitable for scenarios requiring simulation re-run

    About enable_graph_memory_update:
        - When enabled, all agent activities during simulation (posting, commenting, liking, etc.) will be updated to knowledge graph in real-time
        - This allows the graph to "remember" the simulation process, for subsequent analysis or AI conversation
        - Requires the associated project to have a valid graph_id
        - Uses batch update mechanism to reduce API call frequency

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "process_pid": 12345,
                "twitter_running": true,
                "reddit_running": true,
                "started_at": "2025-12-01T10:00:00",
                "graph_memory_update_enabled": true,  // Whether graph memory update is enabled
                "force_restarted": true               // Whether it was a forced restart
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        platform = data.get('platform', 'parallel')
        max_rounds = data.get('max_rounds')  # Optional: maximum simulation rounds
        enable_graph_memory_update = data.get('enable_graph_memory_update', False)  # Optional: whether to enable graph memory update
        force = data.get('force', False)  # Optional: force restart
        resume = data.get('resume', False)  # Optional: resume from last round

        # If resume requested, read the last round from run_state
        start_round = 0
        if resume:
            existing_state = SimulationRunner.get_run_state(simulation_id)
            if existing_state and existing_state.current_round > 0:
                start_round = existing_state.current_round
                logger.info(f"Resuming simulation {simulation_id} from round {start_round}")

        # Validate max_rounds parameter
        if max_rounds is not None:
            try:
                max_rounds = int(max_rounds)
                if max_rounds <= 0:
                    return jsonify({
                        "success": False,
                        "error": "max_rounds must be a positive integer"
                    }), 400
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "error": "max_rounds must be a valid integer"
                }), 400

        if platform not in ['twitter', 'reddit', 'polymarket', 'parallel']:
            return jsonify({
                "success": False,
                "error": f"Invalid platform type: {platform}, options: twitter/reddit/polymarket/parallel"
            }), 400

        enable_cross_platform = data.get('enable_cross_platform', True)

        # Check if simulation is ready
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)

        if not state:
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        force_restarted = False
        
        # Smart status handling: if preparation is complete, allow restart
        if state.status != SimulationStatus.READY:
            # Check if preparation is complete
            is_prepared, prepare_info = _check_simulation_prepared(simulation_id)

            if is_prepared:
                # Preparation complete, check if there is a running process
                if state.status == SimulationStatus.RUNNING:
                    # Check if simulation process is actually running
                    run_state = SimulationRunner.get_run_state(simulation_id)
                    if run_state and run_state.runner_status.value == "running":
                        # Process is actually running
                        if force:
                            # Force mode: stopping running simulation
                            logger.info(f"Force mode: stopping running simulation {simulation_id}")
                            try:
                                SimulationRunner.stop_simulation(simulation_id)
                            except Exception as e:
                                logger.warning(f"Warning while stopping simulation: {str(e)}")
                        else:
                            return jsonify({
                                "success": False,
                                "error": "Simulation is running, please call /stop endpoint to stop first, or use force=true to force restart"
                            }), 400

                # If force mode (and not resuming), clean up run logs
                if force and not resume:
                    logger.info(f"Force mode: cleaning simulation logs {simulation_id}")
                    cleanup_result = SimulationRunner.cleanup_simulation_logs(simulation_id)
                    if not cleanup_result.get("success"):
                        logger.warning(f"Warning while cleaning logs: {cleanup_result.get('errors')}")
                    force_restarted = True

                # Process does not exist or has ended, reset status to ready
                logger.info(f"Simulation {simulation_id} preparation complete, reset status to ready (previous status: {state.status.value})")
                state.status = SimulationStatus.READY
                manager._save_simulation_state(state)
            else:
                # Preparation incomplete
                return jsonify({
                    "success": False,
                    "error": f"Simulation not ready, current status: {state.status.value}, please call /prepare endpoint first"
                }), 400
        
        # Get graph ID (for graph memory update)
        graph_id = None
        if enable_graph_memory_update:
            # Get graph_id from simulation state or project
            graph_id = state.graph_id
            if not graph_id:
                # Try to get from project
                project = ProjectManager.get_project(state.project_id)
                if project:
                    graph_id = project.graph_id
            
            if not graph_id:
                return jsonify({
                    "success": False,
                    "error": "Enabling graph memory update requires a valid graph_id, please ensure the project has built a graph"
                }), 400
            
            logger.info(f"Enable graph memory update: simulation_id={simulation_id}, graph_id={graph_id}")
        
        # Get storage for graph memory update if enabled
        sim_storage = None
        if enable_graph_memory_update:
            sim_storage = current_app.extensions.get('neo4j_storage')

        # Start simulation
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform=platform,
            max_rounds=max_rounds,
            enable_graph_memory_update=enable_graph_memory_update,
            graph_id=graph_id,
            storage=sim_storage,
            start_round=start_round,
            enable_cross_platform=enable_cross_platform,
        )
        
        # Update simulation status
        state.status = SimulationStatus.RUNNING
        manager._save_simulation_state(state)
        
        response_data = run_state.to_dict()
        if max_rounds:
            response_data['max_rounds_applied'] = max_rounds
        response_data['graph_memory_update_enabled'] = enable_graph_memory_update
        response_data['force_restarted'] = force_restarted
        response_data['resumed'] = resume and start_round > 0
        if start_round > 0:
            response_data['resumed_from_round'] = start_round
        if enable_graph_memory_update:
            response_data['graph_id'] = graph_id
        
        return jsonify({
            "success": True,
            "data": response_data
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/stop', methods=['POST'])
def stop_simulation():
    """
    Stop simulation

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // Required, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "stopped",
                "completed_at": "2025-12-01T12:00:00"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        run_state = SimulationRunner.stop_simulation(simulation_id)
        
        # Update simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.PAUSED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to stop simulation: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Real-time Status Monitoring Endpoints ==============

@simulation_bp.route('/<simulation_id>/run-status', methods=['GET'])
def get_run_status(simulation_id: str):
    """
    Get simulation real-time running status (for frontend polling)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                "total_rounds": 144,
                "progress_percent": 3.5,
                "simulated_hours": 2,
                "total_simulation_hours": 72,
                "twitter_running": true,
                "reddit_running": true,
                "twitter_actions_count": 150,
                "reddit_actions_count": 200,
                "total_actions_count": 350,
                "started_at": "2025-12-01T10:00:00",
                "updated_at": "2025-12-01T10:30:00"
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "current_round": 0,
                    "total_rounds": 0,
                    "progress_percent": 0,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            })
        
        return jsonify({
            "success": True,
            "data": run_state.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get running status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/run-status/detail', methods=['GET'])
def get_run_status_detail(simulation_id: str):
    """
    Get simulation detailed running status (including all actions)

    For frontend real-time display

    Query parameters:
        platform: Filter platform (twitter/reddit, optional)

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "runner_status": "running",
                "current_round": 5,
                ...
                "all_actions": [
                    {
                        "round_num": 5,
                        "timestamp": "2025-12-01T10:30:00",
                        "platform": "twitter",
                        "agent_id": 3,
                        "agent_name": "Agent Name",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "..."},
                        "result": null,
                        "success": true
                    },
                    ...
                ],
                "twitter_actions": [...],  # All actions on Twitter platform
                "reddit_actions": [...]    # All actions on Reddit platform
            }
        }
    """
    try:
        run_state = SimulationRunner.get_run_state(simulation_id)
        platform_filter = request.args.get('platform')
        
        if not run_state:
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "runner_status": "idle",
                    "all_actions": [],
                    "twitter_actions": [],
                    "reddit_actions": []
                }
            })
        
        # Get complete action list
        all_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter
        )
        
        # Get actions by platform
        twitter_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="twitter"
        ) if not platform_filter or platform_filter == "twitter" else []
        
        reddit_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform="reddit"
        ) if not platform_filter or platform_filter == "reddit" else []
        
        # Get current round actions (recent_actions only shows latest round)
        current_round = run_state.current_round
        recent_actions = SimulationRunner.get_all_actions(
            simulation_id=simulation_id,
            platform=platform_filter,
            round_num=current_round
        ) if current_round > 0 else []
        
        # Get basic status information
        result = run_state.to_dict()
        result["all_actions"] = [a.to_dict() for a in all_actions]
        result["twitter_actions"] = [a.to_dict() for a in twitter_actions]
        result["reddit_actions"] = [a.to_dict() for a in reddit_actions]
        result["rounds_count"] = len(run_state.rounds)
        # recent_actions only shows current latest round content for both platforms
        result["recent_actions"] = [a.to_dict() for a in recent_actions]
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get detailed status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/actions', methods=['GET'])
def get_simulation_actions(simulation_id: str):
    """
    Get agent action history during simulation

    Query parameters:
        limit: Return count (default 100)
        offset: Offset (default 0)
        platform: Filter platform (twitter/reddit)
        agent_id: Filter Agent ID
        round_num: Filter round

    Returns:
        {
            "success": true,
            "data": {
                "count": 100,
                "actions": [...]
            }
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        platform = request.args.get('platform')
        agent_id = request.args.get('agent_id', type=int)
        round_num = request.args.get('round_num', type=int)
        
        actions = SimulationRunner.get_actions(
            simulation_id=simulation_id,
            limit=limit,
            offset=offset,
            platform=platform,
            agent_id=agent_id,
            round_num=round_num
        )
        
        return jsonify({
            "success": True,
            "data": {
                "count": len(actions),
                "actions": [a.to_dict() for a in actions]
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get action history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/timeline', methods=['GET'])
def get_simulation_timeline(simulation_id: str):
    """
    Get simulation timeline (summarized by round)

    For frontend progress bar and timeline view

    Query parameters:
        start_round: Start round (default 0)
        end_round: End round (default all)

    Returns summary info per round
    """
    try:
        start_round = request.args.get('start_round', 0, type=int)
        end_round = request.args.get('end_round', type=int)
        
        timeline = SimulationRunner.get_timeline(
            simulation_id=simulation_id,
            start_round=start_round,
            end_round=end_round
        )
        
        return jsonify({
            "success": True,
            "data": {
                "rounds_count": len(timeline),
                "timeline": timeline
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get timeline: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/<simulation_id>/agent-stats', methods=['GET'])
def get_agent_stats(simulation_id: str):
    """
    Get statistics for each agent

    For frontend agent activity ranking, action distribution, etc.
    """
    try:
        stats = SimulationRunner.get_agent_stats(simulation_id)
        
        return jsonify({
            "success": True,
            "data": {
                "agents_count": len(stats),
                "stats": stats
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get agent statistics: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Influence Leaderboard ==============


def _compute_influence_ranked(simulation_id, top_n=None):
    """
    Compute agent influence scores from simulation action JSONL logs.

    Reads twitter/actions.jsonl, reddit/actions.jsonl, and polymarket/actions.jsonl,
    then ranks agents by a composite influence score:

        score = engagement_received * 3 + follows_received * 2
                + platform_count * 5 + posts_created

    Returns a list of ranked agent dicts (1-based rank), optionally truncated to top_n.
    Returns an empty list if the simulation directory does not exist.
    """
    sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
    if not os.path.exists(sim_dir):
        return []

    ENGAGEMENT_TYPES = frozenset({
        'LIKE_POST', 'REPOST', 'QUOTE_POST', 'LIKE_COMMENT',
        'CREATE_COMMENT',
    })

    agents = {}

    def _get_or_create(name):
        if name not in agents:
            agents[name] = {
                'agent_name': name,
                'posts_created': 0,
                'engagement_received': 0,
                'follows_received': 0,
                'platforms': set(),
            }
        return agents[name]

    for platform in ('twitter', 'reddit', 'polymarket'):
        actions_path = os.path.join(sim_dir, platform, 'actions.jsonl')
        if not os.path.exists(actions_path):
            continue

        with open(actions_path, 'r', encoding='utf-8') as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if event.get('event_type') in (
                    'simulation_start', 'round_start', 'round_end', 'simulation_end'
                ):
                    continue

                agent_name = event.get('agent_name')
                if not agent_name:
                    continue

                actor = _get_or_create(agent_name)
                actor['platforms'].add(platform)

                action_type = event.get('action_type', '')
                args = event.get('action_args') or {}

                if action_type == 'CREATE_POST':
                    actor['posts_created'] += 1

                elif action_type in ENGAGEMENT_TYPES:
                    author = (
                        args.get('post_author_name')
                        or args.get('original_author_name')
                    )
                    if author and author != agent_name:
                        _get_or_create(author)['engagement_received'] += 1

                elif action_type == 'FOLLOW':
                    target = args.get('target_user_name')
                    if target:
                        _get_or_create(target)['follows_received'] += 1

    ranked = []
    for a in agents.values():
        platform_count = len(a['platforms'])
        score = (
            a['engagement_received'] * 3
            + a['follows_received'] * 2
            + platform_count * 5
            + a['posts_created']
        )
        ranked.append({
            'agent_name': a['agent_name'],
            'posts_created': a['posts_created'],
            'engagement_received': a['engagement_received'],
            'follows_received': a['follows_received'],
            'platform_count': platform_count,
            'platforms': sorted(a['platforms']),
            'influence_score': score,
        })

    ranked.sort(key=lambda x: x['influence_score'], reverse=True)

    for i, entry in enumerate(ranked):
        entry['rank'] = i + 1

    return ranked[:top_n] if top_n else ranked


@simulation_bp.route('/<simulation_id>/influence', methods=['GET'])
def get_influence_leaderboard(simulation_id: str):
    """
    Compute agent influence scores from simulation action JSONL logs.
    Returns the top 20 agents sorted by score descending.
    """
    try:
        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({"success": False, "error": f"Simulation not found: {simulation_id}"}), 404

        ranked = _compute_influence_ranked(simulation_id, top_n=20)

        return jsonify({
            "success": True,
            "data": {
                "agents": ranked,
                "total_agents": len(ranked),
            }
        })

    except Exception as e:
        logger.error(f"Failed to compute influence leaderboard: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Database Query Endpoints ==============

@simulation_bp.route('/<simulation_id>/posts', methods=['GET'])
def get_simulation_posts(simulation_id: str):
    """
    Get simulation posts

    Query parameters:
        platform: Platform type (twitter/reddit)
        limit: Return count (default 50)
        offset: Offset

    Returns post list (read from SQLite database)
    """
    try:
        platform = request.args.get('platform', 'reddit')
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        sim_dir = os.path.join(
            os.path.dirname(__file__),
            f'../../uploads/simulations/{simulation_id}'
        )
        
        db_file = f"{platform}_simulation.db"
        db_path = os.path.join(sim_dir, db_file)
        
        if not os.path.exists(db_path):
            return jsonify({
                "success": True,
                "data": {
                    "platform": platform,
                    "count": 0,
                    "posts": [],
                    "message": "Database does not exist, simulation may not have started"
                }
            })
        
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM post 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            posts = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT COUNT(*) FROM post")
            total = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            posts = []
            total = 0
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "platform": platform,
                "total": total,
                "count": len(posts),
                "posts": posts
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get posts: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Interview Endpoints ==============

@simulation_bp.route('/interview', methods=['POST'])
def interview_agent():
    """
    Interview single agent

    Note: This feature requires the simulation environment to be running
    (after completing simulation loop, entering command waiting mode)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                      // Required, simulation ID
            "agent_id": 0,                                    // Required, Agent ID
            "prompt": "What do you think about this?",        // Required, interview question
            "platform": "twitter",                            // Optional, specify platform (twitter/reddit)
                                                              // When not specified: dual-platform simulation interviews both platforms simultaneously
            "timeout": 60                                     // Optional, timeout (seconds), default 60
        }

    Returns (without specifying platform, dual-platform mode):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "prompt": "...",
                    "platforms": {
                        "twitter": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit": {"agent_id": 0, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }

    Returns (with specified platform):
        {
            "success": true,
            "data": {
                "agent_id": 0,
                "prompt": "What do you think about this?",
                "result": {
                    "agent_id": 0,
                    "response": "I think...",
                    "platform": "twitter",
                    "timestamp": "2025-12-08T10:00:00"
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        agent_id = data.get('agent_id')
        prompt = data.get('prompt')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 60)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        if agent_id is None:
            return jsonify({
                "success": False,
                "error": "Please provide agent_id"
            }), 400
        
        if not prompt:
            return jsonify({
                "success": False,
                "error": "Please provide prompt (interview question)"
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform parameter can only be 'twitter' or 'reddit'"
            }), 400

        # Check environment status — auto-restart if needed
        if not _ensure_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "Simulation environment could not be started. Please try again."
            }), 400

        # Optimize prompt, add prefix to prevent agent from calling tools
        optimized_prompt = optimize_interview_prompt(prompt)
        
        result = SimulationRunner.interview_agent(
            simulation_id=simulation_id,
            agent_id=agent_id,
            prompt=optimized_prompt,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for interview response: {str(e)}"
        }), 504
        
    except Exception as e:
        logger.error(f"Interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/batch', methods=['POST'])
def interview_agents_batch():
    """
    Batch interview multiple agents

    Note: This feature requires the simulation environment to be running

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",                  // Required, simulation ID
            "interviews": [                               // Required, interview list
                {
                    "agent_id": 0,
                    "prompt": "What do you think about A?",
                    "platform": "twitter"                 // Optional, specify interview platform for this agent
                },
                {
                    "agent_id": 1,
                    "prompt": "What do you think about B?"  // If platform not specified, uses default
                }
            ],
            "platform": "reddit",                         // Optional, default platform (overridden by each item's platform)
                                                          // When not specified: dual-platform simulation interviews each agent on both platforms simultaneously
            "timeout": 120                                // Optional, timeout (seconds), default 120
        }

    Returns:
        {
            "success": true,
            "data": {
                "interviews_count": 2,
                "result": {
                    "interviews_count": 4,
                    "results": {
                        "twitter_0": {"agent_id": 0, "response": "...", "platform": "twitter"},
                        "reddit_0": {"agent_id": 0, "response": "...", "platform": "reddit"},
                        "twitter_1": {"agent_id": 1, "response": "...", "platform": "twitter"},
                        "reddit_1": {"agent_id": 1, "response": "...", "platform": "reddit"}
                    }
                },
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        interviews = data.get('interviews')
        platform = data.get('platform')  # Optional: twitter/reddit/None
        timeout = data.get('timeout', 120)

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not interviews or not isinstance(interviews, list):
            return jsonify({
                "success": False,
                "error": "Please provide interviews (interview list)"
            }), 400

        # Validate platform parameter
        if platform and platform not in ("twitter", "reddit"):
            return jsonify({
                "success": False,
                "error": "platform parameter can only be 'twitter' or 'reddit'"
            }), 400

        # Validate each interview item
        for i, interview in enumerate(interviews):
            if 'agent_id' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} is missing agent_id"
                }), 400
            if 'prompt' not in interview:
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} is missing prompt"
                }), 400
            # Validate each item's platform (if present)
            item_platform = interview.get('platform')
            if item_platform and item_platform not in ("twitter", "reddit"):
                return jsonify({
                    "success": False,
                    "error": f"Interview list item {i+1} platform can only be 'twitter' or 'reddit'"
                }), 400

        # Check environment status — auto-restart if needed
        if not _ensure_env_alive(simulation_id):
            return jsonify({
                "success": False,
                "error": "Simulation environment could not be started. Please try again."
            }), 400

        # Optimize each interview item's prompt, add prefix to prevent agent from calling tools
        optimized_interviews = []
        for interview in interviews:
            optimized_interview = interview.copy()
            optimized_interview['prompt'] = optimize_interview_prompt(interview.get('prompt', ''))
            optimized_interviews.append(optimized_interview)

        result = SimulationRunner.interview_agents_batch(
            simulation_id=simulation_id,
            interviews=optimized_interviews,
            platform=platform,
            timeout=timeout
        )

        return jsonify({
            "success": result.get("success", False),
            "data": result
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except TimeoutError as e:
        return jsonify({
            "success": False,
            "error": f"Timed out waiting for batch interview response: {str(e)}"
        }), 504

    except Exception as e:
        logger.error(f"Batch interview failed: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/interview/history', methods=['POST'])
def get_interview_history():
    """
    Get interview history

    Read all interview records from simulation database

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // Required, simulation ID
            "platform": "reddit",          // Optional, platform type (reddit/twitter)
                                           // If not specified, return all history for both platforms
            "agent_id": 0,                 // Optional, only get this agent's interview history
            "limit": 100                   // Optional, return count, default 100
        }

    Returns:
        {
            "success": true,
            "data": {
                "count": 10,
                "history": [
                    {
                        "agent_id": 0,
                        "response": "I think...",
                        "prompt": "What do you think about this?",
                        "timestamp": "2025-12-08T10:00:00",
                        "platform": "reddit"
                    },
                    ...
                ]
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        platform = data.get('platform')  # If not specified, return history for both platforms
        agent_id = data.get('agent_id')
        limit = data.get('limit', 100)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        history = SimulationRunner.get_interview_history(
            simulation_id=simulation_id,
            platform=platform,
            agent_id=agent_id,
            limit=limit
        )

        return jsonify({
            "success": True,
            "data": {
                "count": len(history),
                "history": history
            }
        })

    except Exception as e:
        logger.error(f"Failed to get interview history: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/env-status', methods=['POST'])
def get_env_status():
    """
    Get simulation environment status

    Check if simulation environment is alive (can receive interview commands)

    Request (JSON):
        {
            "simulation_id": "sim_xxxx"  // Required, simulation ID
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "env_alive": true,
                "twitter_available": true,
                "reddit_available": true,
                "message": "Environment is running, can receive interview commands"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        env_alive = SimulationRunner.check_env_alive(simulation_id)
        
        # Get more detailed status information
        env_status = SimulationRunner.get_env_status_detail(simulation_id)

        if env_alive:
            message = "Environment is running, can receive interview commands"
        else:
            message = "Environment is not running or has been shut down"

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "env_alive": env_alive,
                "twitter_available": env_status.get("twitter_available", False),
                "reddit_available": env_status.get("reddit_available", False),
                "message": message
            }
        })

    except Exception as e:
        logger.error(f"Failed to get environment status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/restart-env', methods=['POST'])
def restart_env():
    """
    Restart simulation environment for interviews (without running simulation).
    Launches the simulation script with --env-only flag.
    """
    try:
        data = request.get_json() or {}
        simulation_id = data.get('simulation_id')

        if not simulation_id:
            return jsonify({"success": False, "error": "Please provide simulation_id"}), 400

        # Check if env is already alive
        if SimulationRunner.check_env_alive(simulation_id):
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "message": "Environment is already running",
                    "already_running": True
                }
            })

        # Check if simulation is prepared
        is_prepared, _ = _check_simulation_prepared(simulation_id)
        if not is_prepared:
            return jsonify({"success": False, "error": "Simulation not prepared"}), 400

        # Start the simulation script with --env-only
        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id,
            platform='parallel',
            start_round=0,
            env_only=True
        )

        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "process_pid": run_state.process_pid,
                "message": "Environment starting for interviews",
                "already_running": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to restart env: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@simulation_bp.route('/close-env', methods=['POST'])
def close_simulation_env():
    """
    Shut down simulation environment

    Send shutdown command to simulation for graceful exit from command waiting mode.

    Note: This is different from /stop endpoint. /stop will forcefully terminate the process,
    while this endpoint allows the simulation to gracefully shut down and exit.

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",  // Required, simulation ID
            "timeout": 30                  // Optional, timeout (seconds), default 30
        }

    Returns:
        {
            "success": true,
            "data": {
                "message": "Environment shutdown command sent",
                "result": {...},
                "timestamp": "2025-12-08T10:00:01"
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        simulation_id = data.get('simulation_id')
        timeout = data.get('timeout', 30)
        
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        result = SimulationRunner.close_simulation_env(
            simulation_id=simulation_id,
            timeout=timeout
        )
        
        # Update simulation status
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        if state:
            state.status = SimulationStatus.COMPLETED
            manager._save_simulation_state(state)
        
        return jsonify({
            "success": result.get("success", False),
            "data": result
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    except Exception as e:
        logger.error(f"Failed to shut down environment: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Data Export Endpoints ==============

@simulation_bp.route('/<simulation_id>/export', methods=['GET'])
def export_simulation_data(simulation_id: str):
    """
    Export simulation data as JSON or CSV file download.

    Query parameters:
        format: Export format — 'json' (default) or 'csv'
        include: Comma-separated data sections to include.
                 Options: actions,posts,timeline,agent_stats,metadata
                 Default: all sections

    Returns:
        File download (application/json or text/csv)
    """
    try:
        export_format = request.args.get('format', 'json').lower()
        include_raw = request.args.get('include', 'actions,posts,timeline,agent_stats,metadata')
        include_sections = {s.strip() for s in include_raw.split(',')}

        if export_format not in ('json', 'csv'):
            return jsonify({
                "success": False,
                "error": "Unsupported format. Use 'json' or 'csv'."
            }), 400

        export_data = {}

        # --- Metadata ---
        if 'metadata' in include_sections:
            manager = SimulationManager()
            state = manager.get_simulation(simulation_id)
            run_state = SimulationRunner.get_run_state(simulation_id)
            export_data['metadata'] = {
                "simulation_id": simulation_id,
                "exported_at": datetime.utcnow().isoformat(),
                "status": state.status.value if state else None,
                "project_id": state.project_id if state else None,
                "run_state": run_state.to_dict() if run_state else None,
            }

        # --- Actions ---
        if 'actions' in include_sections:
            actions = SimulationRunner.get_all_actions(simulation_id)
            export_data['actions'] = [a.to_dict() for a in actions]

        # --- Timeline ---
        if 'timeline' in include_sections:
            export_data['timeline'] = SimulationRunner.get_timeline(simulation_id)

        # --- Agent Stats ---
        if 'agent_stats' in include_sections:
            export_data['agent_stats'] = SimulationRunner.get_agent_stats(simulation_id)

        # --- Posts (both platforms) ---
        if 'posts' in include_sections:
            import sqlite3
            sim_dir = os.path.join(
                os.path.dirname(__file__),
                f'../../uploads/simulations/{simulation_id}'
            )
            all_posts = []
            for platform in ('twitter', 'reddit'):
                db_path = os.path.join(sim_dir, f"{platform}_simulation.db")
                if os.path.exists(db_path):
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM post ORDER BY created_at DESC")
                        for row in cursor.fetchall():
                            post = dict(row)
                            post['platform'] = platform
                            all_posts.append(post)
                        conn.close()
                    except sqlite3.OperationalError:
                        pass
            export_data['posts'] = all_posts

        # --- Build response ---
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename_base = f"miroshark_export_{simulation_id[:12]}_{timestamp}"

        if export_format == 'json':
            buf = io.BytesIO()
            buf.write(json.dumps(export_data, indent=2, default=str, ensure_ascii=False).encode('utf-8'))
            buf.seek(0)
            return send_file(
                buf,
                mimetype='application/json',
                as_attachment=True,
                download_name=f"{filename_base}.json"
            )

        # CSV: flatten actions into a single table (the most useful tabular view)
        rows = export_data.get('actions', [])
        if not rows:
            return jsonify({
                "success": False,
                "error": "No action data available to export as CSV"
            }), 404

        fieldnames = ['round_num', 'timestamp', 'platform', 'agent_id',
                      'agent_name', 'action_type', 'action_args', 'result', 'success']

        string_buf = io.StringIO()
        writer = csv.DictWriter(string_buf, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            row_copy = dict(row)
            # Serialize nested dicts to JSON strings for CSV
            if isinstance(row_copy.get('action_args'), dict):
                row_copy['action_args'] = json.dumps(row_copy['action_args'], ensure_ascii=False)
            writer.writerow(row_copy)

        buf = io.BytesIO()
        buf.write(string_buf.getvalue().encode('utf-8'))
        buf.seek(0)
        return send_file(
            buf,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{filename_base}.csv"
        )

    except Exception as e:
        logger.error(f"Failed to export simulation data: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Simulation Comparison Endpoint ==============

@simulation_bp.route('/compare', methods=['GET'])
def compare_simulations():
    """
    Compare two completed simulations side by side.

    Query parameters:
        id1: First simulation ID (required)
        id2: Second simulation ID (required)

    Returns aggregated comparison data from both simulations:
    - Influence leaderboards (top 10 each)
    - Per-round activity timelines
    - Prediction market final prices (from polymarket SQLite if available)
    - Divergence score (0–1, higher = more divergent outcomes)

    Divergence score methodology:
        For each agent that appears in the top-10 of both runs, compute the
        normalized absolute rank difference. Agents present in one run but not
        the other contribute a penalty of 0.5 per missing agent. The final score
        is the mean across all compared agents, clamped to [0, 1].
    """
    try:
        id1 = request.args.get('id1', '').strip()
        id2 = request.args.get('id2', '').strip()

        if not id1 or not id2:
            return jsonify({"success": False, "error": "Both id1 and id2 are required"}), 400

        if id1 == id2:
            return jsonify({"success": False, "error": "id1 and id2 must be different simulations"}), 400

        def _load_state(sim_id):
            m = SimulationManager()
            return m.get_simulation(sim_id)

        def _load_timeline_summary(sim_id):
            """Load and summarise timeline: per-round total actions, total rounds."""
            timeline = SimulationRunner.get_timeline(sim_id)
            return [
                {
                    'round_num': r['round_num'],
                    'total_actions': r['total_actions'],
                    'twitter_actions': r['twitter_actions'],
                    'reddit_actions': r['reddit_actions'],
                }
                for r in timeline
            ]

        def _load_market_prices(sim_id):
            """
            Extract per-round YES token prices from the Polymarket SQLite database.

            Reads the AmM reserve table to derive price_yes = reserve_no / (reserve_yes + reserve_no)
            per round. Returns an empty list if Polymarket was not enabled or the DB does not exist.
            """
            sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, sim_id)
            db_path = os.path.join(sim_dir, 'polymarket', 'polymarket.db')
            if not os.path.exists(db_path):
                return []
            try:
                import sqlite3
                con = sqlite3.connect(db_path)
                cur = con.cursor()
                # Try to read round-level price snapshots if they exist
                tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                prices = []

                if 'price_history' in tables:
                    # Custom table we may have written
                    rows = cur.execute(
                        "SELECT round_num, market_id, price_yes FROM price_history ORDER BY round_num, market_id"
                    ).fetchall()
                    for rn, mid, py in rows:
                        prices.append({'round_num': rn, 'market_id': mid, 'price_yes': py})
                elif 'market' in tables:
                    # Wonderwall market table: id, reserve_yes, reserve_no
                    rows = cur.execute(
                        "SELECT id, reserve_yes, reserve_no FROM market"
                    ).fetchall()
                    for mid, ry, rn in rows:
                        total = (ry or 0) + (rn or 0)
                        price_yes = (rn / total) if total > 0 else 0.5
                        prices.append({'market_id': mid, 'price_yes': round(price_yes, 4), 'round_num': None})
                con.close()
                return prices
            except Exception:
                return []

        # Load data for both simulations
        state1 = _load_state(id1)
        state2 = _load_state(id2)

        if not state1:
            return jsonify({"success": False, "error": f"Simulation not found: {id1}"}), 404
        if not state2:
            return jsonify({"success": False, "error": f"Simulation not found: {id2}"}), 404

        influence1 = _compute_influence_ranked(id1, top_n=10)
        influence2 = _compute_influence_ranked(id2, top_n=10)
        timeline1 = _load_timeline_summary(id1)
        timeline2 = _load_timeline_summary(id2)
        markets1 = _load_market_prices(id1)
        markets2 = _load_market_prices(id2)

        # ---- Divergence Score ----
        # Rank-based divergence: normalized mean absolute rank difference for top-10 agents
        rank_map1 = {a['agent_name']: a['rank'] for a in influence1}
        rank_map2 = {a['agent_name']: a['rank'] for a in influence2}
        all_agents = set(rank_map1) | set(rank_map2)
        if all_agents:
            diffs = []
            for name in all_agents:
                r1 = rank_map1.get(name, 15)  # penalty: treat absent agents as rank 15
                r2 = rank_map2.get(name, 15)
                diffs.append(abs(r1 - r2) / 14.0)  # normalise to [0, 1] (max diff = 14)
            divergence_score = round(min(1.0, sum(diffs) / len(diffs)), 3)
        else:
            divergence_score = 0.0

        # ---- Total activity stats ----
        def _total_actions(timeline):
            return sum(r['total_actions'] for r in timeline)

        return jsonify({
            "success": True,
            "data": {
                "id1": id1,
                "id2": id2,
                "divergence_score": divergence_score,
                "sim1": {
                    "simulation_id": id1,
                    "status": state1.status.value if state1 else None,
                    "profiles_count": state1.profiles_count if state1 else 0,
                    "total_rounds": len(timeline1),
                    "total_actions": _total_actions(timeline1),
                    "influence": influence1,
                    "timeline": timeline1,
                    "markets": markets1,
                },
                "sim2": {
                    "simulation_id": id2,
                    "status": state2.status.value if state2 else None,
                    "profiles_count": state2.profiles_count if state2 else 0,
                    "total_rounds": len(timeline2),
                    "total_actions": _total_actions(timeline2),
                    "influence": influence2,
                    "timeline": timeline2,
                    "markets": markets2,
                },
            }
        })

    except Exception as e:
        logger.error(f"Failed to compare simulations: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


# ============== Article Generator ==============

@simulation_bp.route('/<simulation_id>/article', methods=['POST'])
def generate_simulation_article(simulation_id: str):
    """
    Generate a 400-600 word publishable article brief from simulation results.

    Returns a Substack-style article with abstract, key findings, market dynamics,
    implications, and a caveats paragraph. Result is cached in generated_article.json
    inside the simulation directory so re-opening the drawer does not re-call the LLM.

    Request body (JSON, optional):
        {
            "force_regenerate": false,    // Re-generate even if cached
            "share_url": "https://..."    // Optional share permalink to append
        }

    Returns:
        {
            "success": true,
            "data": {
                "article_text": "...",
                "cached": false
            }
        }
    """
    try:
        body = request.get_json(silent=True) or {}
        force_regenerate = body.get('force_regenerate', False)
        share_url = body.get('share_url', '')

        sim_dir = os.path.join(Config.WONDERWALL_SIMULATION_DATA_DIR, simulation_id)
        if not os.path.exists(sim_dir):
            return jsonify({
                "success": False,
                "error": f"Simulation not found: {simulation_id}"
            }), 404

        # --- Cache check ---
        cache_path = os.path.join(sim_dir, 'generated_article.json')
        if not force_regenerate and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                return jsonify({
                    "success": True,
                    "data": {
                        "article_text": cached.get('article_text', ''),
                        "cached": True
                    }
                })
            except Exception:
                pass  # corrupt cache — fall through to regenerate

        # --- Gather context ---
        manager = SimulationManager()
        state = manager.get_simulation(simulation_id)
        config = manager.get_simulation_config(simulation_id)

        scenario = ''
        if config:
            scenario = config.get('simulation_requirement', '')
        if not scenario and state:
            scenario = getattr(state, 'simulation_requirement', '') or ''

        run_state = SimulationRunner.get_run_state(simulation_id)
        total_rounds = 0
        agent_count = 0
        if run_state:
            total_rounds = run_state.current_round
        if state:
            agent_count = state.profiles_count

        # Top 5 most active rounds from timeline
        timeline = SimulationRunner.get_timeline(simulation_id)
        top_rounds = sorted(timeline, key=lambda r: r['total_actions'], reverse=True)[:5]
        top_rounds_summary = ', '.join(
            f"round {r['round_num']} ({r['total_actions']} actions)"
            for r in top_rounds
        )

        # Top 3 influence leaders
        leaders = _compute_influence_ranked(simulation_id, top_n=3)
        leader_lines = []
        for agent in leaders:
            name = agent.get('agent_name', 'Unknown')
            score = agent.get('score', 0)
            posts = agent.get('posts_created', 0)
            engagement = agent.get('engagement_received', 0)
            leader_lines.append(
                f"- {name}: influence score {score}, {posts} posts, {engagement} engagements received"
            )
        leaders_text = '\n'.join(leader_lines) if leader_lines else 'No agent data available.'

        # Market price from Polymarket DB (if enabled)
        market_summary = ''
        polymarket_db = os.path.join(sim_dir, 'polymarket', 'polymarket.db')
        if os.path.exists(polymarket_db):
            try:
                import sqlite3
                con = sqlite3.connect(polymarket_db)
                cur = con.cursor()
                tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'market' in tables:
                    rows = cur.execute("SELECT id, reserve_yes, reserve_no FROM market").fetchall()
                    market_lines = []
                    for mid, ry, rn in rows:
                        total = (ry or 0) + (rn or 0)
                        price_yes = round((rn / total) * 100, 1) if total > 0 else 50.0
                        market_lines.append(f"Market {mid}: {price_yes}% YES")
                    market_summary = '; '.join(market_lines)
                con.close()
            except Exception:
                pass

        market_context = (
            f"\nPrediction market final prices: {market_summary}"
            if market_summary else ""
        )

        share_cta = (
            f"\n\nExplore this simulation yourself: {share_url}"
            if share_url else ""
        )

        # --- LLM call ---
        from ..utils.llm_client import create_smart_llm_client

        prompt = f"""You are writing a simulation study brief in the style of a Substack post. Write 400-600 words.

Simulation scenario: {scenario or 'Multi-agent social simulation'}
Total rounds completed: {total_rounds}
Total agents: {agent_count}
Most active rounds: {top_rounds_summary or 'N/A'}{market_context}

Top influence leaders:
{leaders_text}

Write the article with these sections:
1. One-sentence abstract (what was simulated and why it matters)
2. Three bullet-point key findings — be specific, use the data above (active rounds, top agents, market prices if available)
3. One paragraph on agent dynamics (how did the top agents drive the narrative?)
4. One paragraph on implications (what does this simulation tell us about the real-world scenario?)
5. Two-sentence caveat about AI simulation limitations{share_cta}

Return only the article text in Markdown format. Use ## for section headings. Do not include a title — start directly with the abstract."""

        llm = create_smart_llm_client(timeout=120.0)
        article_text = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
        )

        # --- Cache result ---
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'article_text': article_text, 'generated_at': datetime.utcnow().isoformat()}, f)
        except Exception as e:
            logger.warning(f"Failed to cache generated article for {simulation_id}: {e}")

        return jsonify({
            "success": True,
            "data": {
                "article_text": article_text,
                "cached": False
            }
        })

    except Exception as e:
        logger.error(f"Failed to generate article for {simulation_id}: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500
