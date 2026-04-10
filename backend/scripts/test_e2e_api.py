#!/usr/bin/env python3
"""
End-to-end API test — exercises the full MiroShark pipeline via HTTP.

Usage:
    1. Start Neo4j:   docker compose up neo4j -d
    2. Start backend:  cd backend && uv run python run.py
    3. Run test:       cd backend && uv run python scripts/test_e2e_api.py

Pipeline:
    Phase 1: Upload PDF + generate ontology    POST /api/graph/ontology/generate
    Phase 2: Build knowledge graph             POST /api/graph/build  → poll task
    Phase 3: Create simulation                 POST /api/simulation/create
    Phase 4: Prepare simulation (profiles+cfg) POST /api/simulation/prepare → poll task
    Phase 5: Run simulation (3 rounds)         POST /api/simulation/start → poll status
    Phase 6: Generate report                   POST /api/report/generate → poll task
    Phase 7: Retrieve report                   GET  /api/report/{report_id}
"""

import json
import os
import sys
import time
import requests
from datetime import datetime

# ── Configuration ──

BASE_URL = os.environ.get("MIROSHARK_API_URL", "http://localhost:5001")

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))

PDF_PATH = os.path.join(
    _backend_dir, '..',
    'sample_article.pdf'
)

SIMULATION_REQUIREMENT = (
    "Simulate public reaction on Twitter and Reddit to this article. "
    "Focus on: community reactions, discussion threads, and how different "
    "user segments respond to the content."
)

MAX_SIM_ROUNDS = 3          # Keep short for testing
POLL_INTERVAL = 5           # Seconds between status polls
POLL_TIMEOUT = 1800         # Max seconds to wait for any async phase (30 min)

# ── Output ──

OUT_DIR = os.path.join(_backend_dir, 'e2e_test_output')
os.makedirs(OUT_DIR, exist_ok=True)


# ── Helpers ──

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def banner(phase_num, title):
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"  Phase {phase_num}: {title}")
    print(f"{'='*60}{Colors.RESET}")


def ok(msg):
    print(f"  {Colors.GREEN}✓{Colors.RESET} {msg}")


def info(msg):
    print(f"  {Colors.CYAN}→{Colors.RESET} {msg}")


def warn(msg):
    print(f"  {Colors.YELLOW}⚠{Colors.RESET} {msg}")


def fail(msg):
    print(f"  {Colors.RED}✗ {msg}{Colors.RESET}")
    sys.exit(1)


def save_json(name, data):
    path = os.path.join(OUT_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    info(f"Saved: {path}")


def api(method, path, **kwargs):
    """Make an API call, return parsed JSON. Fail on HTTP errors."""
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.request(method, url, timeout=300, **kwargs)
    except requests.ConnectionError:
        fail(f"Cannot connect to {url} — is the backend running?")
    except requests.Timeout:
        fail(f"Request timed out: {method} {path}")

    try:
        body = resp.json()
    except Exception:
        fail(f"Non-JSON response ({resp.status_code}): {resp.text[:300]}")

    if resp.status_code >= 400 or not body.get('success', False):
        error = body.get('error', resp.text[:300])
        fail(f"{method} {path} failed ({resp.status_code}): {error}")

    return body['data']


def poll_task(task_path, task_id, label, method='GET', body=None, timeout=POLL_TIMEOUT):
    """Poll an async task until completed/failed. Returns task result."""
    t0 = time.time()
    last_msg = ""

    while True:
        elapsed = time.time() - t0
        if elapsed > timeout:
            fail(f"{label}: timed out after {timeout}s")

        if method == 'GET':
            data = api('GET', f"{task_path}/{task_id}")
        else:
            payload = body or {}
            data = api('POST', task_path, json=payload)

        status = data.get('status', '')
        progress = data.get('progress', 0)
        message = data.get('message', '')

        # Show progress updates (deduplicate)
        if message and message != last_msg:
            info(f"[{progress}%] {message}")
            last_msg = message

        if status in ('completed', 'ready'):
            return data
        if status == 'failed':
            fail(f"{label} failed: {data.get('message', data.get('error', 'unknown'))}")
        if data.get('already_prepared') or data.get('already_completed'):
            return data

        time.sleep(POLL_INTERVAL)


def poll_simulation(simulation_id, timeout=POLL_TIMEOUT):
    """Poll simulation run-status until runner_status != running."""
    t0 = time.time()
    last_round = -1

    while True:
        elapsed = time.time() - t0
        if elapsed > timeout:
            fail(f"Simulation timed out after {timeout}s")

        data = api('GET', f"/api/simulation/{simulation_id}/run-status")
        status = data.get('runner_status', 'idle')
        current = data.get('current_round', 0)
        total = data.get('total_rounds', 0)
        actions = data.get('total_actions_count', 0)

        if current != last_round:
            info(f"Round {current}/{total} — {actions} actions — status: {status}")
            last_round = current

        if status in ('completed', 'idle', 'stopped', 'failed'):
            return data
        if status == 'error':
            fail(f"Simulation error: {data}")

        time.sleep(POLL_INTERVAL)


# ── Pipeline Phases ──

def phase1_ontology():
    """Upload PDF and generate ontology."""
    banner(1, "Upload PDF + Generate Ontology")
    t0 = time.time()

    if not os.path.exists(PDF_PATH):
        fail(f"PDF not found: {PDF_PATH}")

    info(f"Uploading: {os.path.basename(PDF_PATH)} ({os.path.getsize(PDF_PATH):,} bytes)")

    with open(PDF_PATH, 'rb') as f:
        data = api('POST', '/api/graph/ontology/generate',
                   files={'files': (os.path.basename(PDF_PATH), f, 'application/pdf')},
                   data={
                       'simulation_requirement': SIMULATION_REQUIREMENT,
                       'project_name': 'E2E API Test'
                   })

    project_id = data['project_id']
    ontology = data.get('ontology', {})
    entity_types = ontology.get('entity_types', [])
    edge_types = ontology.get('edge_types', [])

    ok(f"Project: {project_id}")
    ok(f"Entity types ({len(entity_types)}): {', '.join(t.get('name', str(t)) for t in entity_types[:6])}")
    ok(f"Edge types ({len(edge_types)}): {', '.join(t.get('name', str(t)) for t in edge_types[:6])}")
    ok(f"Time: {time.time()-t0:.1f}s")

    save_json('01_ontology', data)
    return project_id


def phase2_graph(project_id):
    """Build knowledge graph (async)."""
    banner(2, "Build Knowledge Graph")
    t0 = time.time()

    data = api('POST', '/api/graph/build', json={
        'project_id': project_id,
        'graph_name': 'E2E Test Graph',
        'chunk_size': 500,
        'chunk_overlap': 50
    })

    task_id = data['task_id']
    info(f"Build task started: {task_id}")

    # Poll until complete
    result = poll_task('/api/graph/task', task_id, 'Graph build')

    # Extract graph_id from task result
    task_result = result.get('result', {})
    graph_id = task_result.get('graph_id')

    if not graph_id:
        # Fallback: read from project
        project = api('GET', f'/api/graph/project/{project_id}')
        graph_id = project.get('graph_id')

    if not graph_id:
        fail("No graph_id returned from build task")

    node_count = task_result.get('node_count', '?')
    edge_count = task_result.get('edge_count', '?')

    ok(f"Graph: {graph_id}")
    ok(f"Nodes: {node_count}, Edges: {edge_count}")
    ok(f"Time: {time.time()-t0:.1f}s")

    # Fetch graph data for verification
    graph_data = api('GET', f'/api/graph/data/{graph_id}')
    save_json('02_graph_data', graph_data)

    return graph_id


def phase3_create_simulation(project_id):
    """Create simulation record."""
    banner(3, "Create Simulation")
    t0 = time.time()

    data = api('POST', '/api/simulation/create', json={
        'project_id': project_id,
        'enable_twitter': True,
        'enable_reddit': True,
    })

    simulation_id = data['simulation_id']
    ok(f"Simulation: {simulation_id}")
    ok(f"Platforms: twitter={data.get('enable_twitter')}, reddit={data.get('enable_reddit')}")
    ok(f"Time: {time.time()-t0:.1f}s")

    save_json('03_simulation_created', data)
    return simulation_id


def phase4_prepare(simulation_id):
    """Prepare simulation — generate profiles + config (async)."""
    banner(4, "Prepare Simulation (Profiles + Config)")
    t0 = time.time()

    data = api('POST', '/api/simulation/prepare', json={
        'simulation_id': simulation_id,
        'use_llm_for_profiles': True,
        'parallel_profile_count': 5
    })

    if data.get('already_prepared'):
        ok("Already prepared (skipped)")
        return

    task_id = data.get('task_id')
    expected = data.get('expected_entities_count', '?')
    info(f"Prepare task started: {task_id} (expected agents: {expected})")

    # Poll until complete — uses POST with body
    result = poll_task(
        '/api/simulation/prepare/status', task_id,
        'Preparation',
        method='POST',
        body={'task_id': task_id, 'simulation_id': simulation_id}
    )

    ok(f"Preparation complete")
    ok(f"Time: {time.time()-t0:.1f}s")

    # Fetch profiles and config for verification
    profiles = api('GET', f'/api/simulation/{simulation_id}/profiles')
    if isinstance(profiles, list):
        ok(f"Profiles generated: {len(profiles)}")
        for p in profiles[:3]:
            info(f"  {p.get('name', '?')} ({p.get('source_entity_type', '?')}) — {p.get('bio', '')[:80]}")
        save_json('04_profiles', profiles)
    elif isinstance(profiles, dict) and 'profiles' in profiles:
        profile_list = profiles['profiles']
        ok(f"Profiles generated: {len(profile_list)}")
        save_json('04_profiles', profiles)
    else:
        save_json('04_profiles', profiles)

    config = api('GET', f'/api/simulation/{simulation_id}/config')
    save_json('04_config', config)


def phase5_run(simulation_id):
    """Run simulation for MAX_SIM_ROUNDS rounds."""
    banner(5, f"Run Simulation ({MAX_SIM_ROUNDS} rounds)")
    t0 = time.time()

    data = api('POST', '/api/simulation/start', json={
        'simulation_id': simulation_id,
        'platform': 'parallel',
        'max_rounds': MAX_SIM_ROUNDS,
        'force': True
    })

    info(f"PID: {data.get('process_pid', '?')}")
    info(f"Platforms: twitter={data.get('twitter_running')}, reddit={data.get('reddit_running')}")

    # Poll until simulation finishes
    result = poll_simulation(simulation_id, timeout=POLL_TIMEOUT)

    actions = result.get('total_actions_count', 0)
    twitter_actions = result.get('twitter_actions_count', 0)
    reddit_actions = result.get('reddit_actions_count', 0)

    ok(f"Simulation finished: {result.get('runner_status')}")
    ok(f"Total actions: {actions} (Twitter: {twitter_actions}, Reddit: {reddit_actions})")
    ok(f"Time: {time.time()-t0:.1f}s")

    save_json('05_run_result', result)

    # Fetch detailed actions
    try:
        detail = api('GET', f'/api/simulation/{simulation_id}/run-status/detail')
        save_json('05_run_detail', detail)
    except SystemExit:
        warn("Could not fetch detailed run status (non-critical)")


def phase6_report(simulation_id):
    """Generate analysis report (async)."""
    banner(6, "Generate Report")
    t0 = time.time()

    data = api('POST', '/api/report/generate', json={
        'simulation_id': simulation_id,
        'force_regenerate': True
    })

    if data.get('already_generated'):
        report_id = data['report_id']
        ok(f"Report already exists: {report_id}")
        return report_id

    report_id = data['report_id']
    task_id = data['task_id']
    info(f"Report task started: {task_id} (report_id: {report_id})")

    # Poll until complete
    result = poll_task(
        '/api/report/generate/status', task_id,
        'Report generation',
        method='POST',
        body={'task_id': task_id, 'simulation_id': simulation_id}
    )

    ok(f"Report generated: {report_id}")
    ok(f"Time: {time.time()-t0:.1f}s")

    return report_id


def phase7_retrieve_report(report_id):
    """Retrieve and display the generated report."""
    banner(7, "Retrieve Report")

    data = api('GET', f'/api/report/{report_id}')

    status = data.get('status', '?')
    markdown = data.get('markdown_content', '')
    sections = data.get('outline', {}).get('sections', [])

    ok(f"Status: {status}")
    ok(f"Sections: {len(sections)}")
    for s in sections:
        title = s.get('title', '?')
        content_len = len(s.get('content', ''))
        info(f"  {title} ({content_len:,} chars)")

    ok(f"Total report length: {len(markdown):,} chars")

    # Save report
    save_json('06_report_meta', data)

    report_path = os.path.join(OUT_DIR, '06_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(markdown)
    info(f"Saved: {report_path}")

    # Print preview
    print(f"\n{Colors.CYAN}--- Report Preview (first 500 chars) ---{Colors.RESET}")
    print(markdown[:500])
    if len(markdown) > 500:
        print(f"... ({len(markdown) - 500:,} more chars)")

    return data


# ── Main ──

def main():
    print(f"\n{Colors.BOLD}{'#'*60}")
    print(f"  MiroShark — End-to-End API Test")
    print(f"  API: {BASE_URL}")
    print(f"  PDF: {os.path.basename(PDF_PATH)}")
    print(f"  Rounds: {MAX_SIM_ROUNDS}")
    print(f"  Output: {OUT_DIR}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}{Colors.RESET}")

    # Preflight: check server is up
    try:
        requests.get(f"{BASE_URL}/api/graph/project/nonexistent", timeout=15)
        ok(f"Backend reachable at {BASE_URL}")
    except (requests.ConnectionError, requests.Timeout):
        fail(f"Backend not reachable at {BASE_URL} — start it with: cd backend && uv run python run.py")

    total_t0 = time.time()

    # Phase 1: Upload + Ontology
    project_id = phase1_ontology()

    # Phase 2: Build Graph
    graph_id = phase2_graph(project_id)

    # Phase 3: Create Simulation
    simulation_id = phase3_create_simulation(project_id)

    # Phase 4: Prepare (profiles + config)
    phase4_prepare(simulation_id)

    # Phase 5: Run Simulation
    phase5_run(simulation_id)

    # Phase 6: Generate Report
    report_id = phase6_report(simulation_id)

    # Phase 7: Retrieve Report
    phase7_retrieve_report(report_id)

    # ── Summary ──
    total_elapsed = time.time() - total_t0
    print(f"\n{Colors.BOLD}{'='*60}")
    print(f"  END-TO-END TEST COMPLETE")
    print(f"{'='*60}{Colors.RESET}")
    ok(f"Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    ok(f"Project:    {project_id}")
    ok(f"Graph:      {graph_id}")
    ok(f"Simulation: {simulation_id}")
    ok(f"Report:     {report_id}")
    print()
    ok(f"Output files:")
    for f in sorted(os.listdir(OUT_DIR)):
        size = os.path.getsize(os.path.join(OUT_DIR, f))
        info(f"  {f} ({size:,} bytes)")
    print()


if __name__ == '__main__':
    main()
