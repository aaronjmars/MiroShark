#!/usr/bin/env python3
"""
Continue pipeline test — Phase 5 (config) + Phase 6 (3-round simulation).

Reuses the graph from the previous run.

Usage:
    cd backend
    .venv/bin/python scripts/test_pipeline_phase5_6.py
"""

import json
import os
import sys
import time
from datetime import datetime

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, '..', '.env'))

from app.config import Config

OUT_DIR = os.path.join(_backend_dir, 'pipeline_test_output')
os.makedirs(OUT_DIR, exist_ok=True)

SIMULATION_REQUIREMENT = (
    "Simulate public reaction on Twitter and Reddit to this article. "
    "Focus on: community reactions, discussion threads, and how different "
    "user segments respond to the content."
)


def save_json(name, data):
    path = os.path.join(OUT_DIR, f'{name}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  → Saved: {path}")


def save_text(name, text):
    path = os.path.join(OUT_DIR, f'{name}.txt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"  → Saved: {path}")


def banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def phase5_config(graph_id, document_text):
    """Generate simulation config using the existing graph."""
    banner("PHASE 5: Generate Simulation Config")
    t0 = time.time()

    from app.storage.neo4j_storage import Neo4jStorage
    from app.services.entity_reader import EntityReader
    from app.services.simulation_config_generator import SimulationConfigGenerator

    storage = Neo4jStorage()
    reader = EntityReader(storage)

    # Load ontology from graph
    ontology = storage.get_ontology(graph_id)
    entity_types = []
    if ontology:
        for et in ontology.get('entity_types', []):
            if isinstance(et, dict):
                entity_types.append(et.get('name', str(et)))
            else:
                entity_types.append(str(et))

    # Get entities from graph
    filtered = reader.filter_defined_entities(
        graph_id=graph_id,
        defined_entity_types=entity_types,
        enrich_with_edges=True,
    )
    print(f"  Entities: {filtered.filtered_count}")
    print(f"  Types: {list(filtered.entity_types)}")

    # Limit to 6 for speed
    test_entities = filtered.entities[:6]
    for e in test_entities:
        print(f"    - {e.name} ({e.get_entity_type()})")

    generator = SimulationConfigGenerator()

    def progress(step, total, msg):
        print(f"    [{step}/{total}] {msg}")

    result = generator.generate_config(
        simulation_id="test_sim_001",
        project_id="test_proj_001",
        graph_id=graph_id,
        simulation_requirement=SIMULATION_REQUIREMENT,
        document_text=document_text[:3000],
        entities=test_entities,
        enable_twitter=True,
        enable_reddit=True,
        progress_callback=progress,
    )

    elapsed = time.time() - t0

    # SimulationParameters has a to_dict method
    config = result.to_dict() if hasattr(result, 'to_dict') else result

    print(f"\n  Time config:")
    tc = config.get('time_config', {})
    print(f"    Total hours: {tc.get('total_simulation_hours')}")
    print(f"    Minutes per round: {tc.get('minutes_per_round')}")

    print(f"  Agent configs: {len(config.get('agent_configs', []))}")
    for ac in config.get('agent_configs', []):
        print(f"    - {ac.get('entity_name', '?')}: activity={ac.get('activity_level')}, "
              f"stance={ac.get('stance')}, sentiment={ac.get('sentiment_bias')}, "
              f"influence={ac.get('influence_weight')}")

    print(f"  Event config:")
    ec = config.get('event_config', {})
    posts = ec.get('initial_posts', [])
    print(f"    Initial posts: {len(posts)}")
    for ip in posts[:3]:
        content = str(ip.get('content', ''))[:120]
        print(f"      - [{ip.get('poster_type', '?')}] {content}")

    topics = ec.get('hot_topics', [])
    if topics:
        print(f"    Hot topics: {topics}")

    print(f"  Time: {elapsed:.1f}s")

    save_json('05_simulation_config', config)
    return config, storage


def phase6_simulation(config, storage, graph_id):
    """Run a 3-round simulation with the generated config."""
    banner("PHASE 6: Run 3-Round Simulation")
    t0 = time.time()

    # We need to set up the simulation directory structure
    sim_dir = os.path.join(OUT_DIR, 'sim_test')
    os.makedirs(sim_dir, exist_ok=True)
    os.makedirs(os.path.join(sim_dir, 'twitter'), exist_ok=True)
    os.makedirs(os.path.join(sim_dir, 'reddit'), exist_ok=True)

    # Override config for quick test: 3 rounds at peak hours
    config['time_config'] = config.get('time_config', {})
    config['time_config']['total_simulation_hours'] = 72
    config['time_config']['minutes_per_round'] = 60
    # Override multipliers so all hours are active for testing
    config['time_config']['off_peak_activity_multiplier'] = 1.0
    config['time_config']['morning_activity_multiplier'] = 1.0
    config['time_config']['work_activity_multiplier'] = 1.0
    config['time_config']['peak_activity_multiplier'] = 1.0
    config['time_config']['agents_per_hour_min'] = 6  # force all agents active
    config['time_config']['agents_per_hour_max'] = 6
    # Force all agents to be active
    for ac in config.get('agent_configs', []):
        ac['activity_level'] = 1.0  # 100% chance of activation
        ac['active_hours'] = list(range(0, 24))

    # Load full profiles from phase 4 if available, otherwise generate minimal ones
    agent_configs = config.get('agent_configs', [])
    profiles_from_phase4 = os.path.join(OUT_DIR, '04_profiles.json')
    phase4_profiles = []
    if os.path.exists(profiles_from_phase4):
        with open(profiles_from_phase4) as f:
            phase4_profiles = json.load(f)
        print(f"  Loaded {len(phase4_profiles)} profiles from Phase 4")

    # Build profile lookup by name
    profile_lookup = {p['name'].lower(): p for p in phase4_profiles}

    reddit_profiles = []
    for i, ac in enumerate(agent_configs):
        entity_name = ac.get('entity_name', f'Agent_{i}')
        # Try to match from phase 4 profiles
        p4 = profile_lookup.get(entity_name.lower(), {})

        reddit_profiles.append({
            "user_id": i + 1,
            "username": (p4.get('user_name') or entity_name.lower().replace(' ', '_')),
            "name": entity_name,
            "bio": p4.get('bio', f"Agent for {ac.get('entity_type', 'Entity')}"),
            "persona": p4.get('persona', f"{entity_name} participates in online discussions."),
            "karma": p4.get('karma', 1000),
            "age": p4.get('age', 30),
            "gender": p4.get('gender', 'other'),
            "mbti": p4.get('mbti', 'INTJ'),
            "country": p4.get('country', 'US'),
            "profession": p4.get('profession', ac.get('entity_type', 'Unknown')),
            "interested_topics": p4.get('interested_topics', ['General']),
            "created_at": "2024-01-01",
        })

    profiles_path = os.path.join(sim_dir, 'reddit_profiles.json')
    with open(profiles_path, 'w') as f:
        json.dump(reddit_profiles, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {len(reddit_profiles)} Reddit profiles")

    # Save config
    config_path = os.path.join(sim_dir, 'simulation_config.json')
    config['simulation_requirement'] = SIMULATION_REQUIREMENT
    with open(config_path, 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  Wrote simulation config")

    # Run Reddit-only simulation (simplest, no CSV needed)
    print(f"\n  Starting Reddit-only simulation (3 rounds)...")
    print(f"  Config: {len(agent_configs)} agents, 3 rounds, 60 min/round")

    import subprocess
    cmd = [
        sys.executable, os.path.join(_scripts_dir, 'run_parallel_simulation.py'),
        '--config', config_path,
        '--reddit-only',
        '--max-rounds', '3',
        '--no-wait',
    ]
    print(f"  Command: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=_backend_dir,
    )

    output_lines = []
    for line in proc.stdout:
        line = line.rstrip()
        output_lines.append(line)
        # Print key lines
        if any(k in line for k in ['Round ', 'Environment ready', 'complete',
                                     'FAILED', 'Error', 'action', 'Starting',
                                     'Published', 'agents active']):
            print(f"    {line}")

    proc.wait()
    elapsed = time.time() - t0

    print(f"\n  Simulation exit code: {proc.returncode}")
    print(f"  Time: {elapsed:.1f}s")

    # Save full output
    save_text('06_simulation_output', '\n'.join(output_lines))

    # Check for action logs
    actions_path = os.path.join(sim_dir, 'reddit', 'actions.jsonl')
    if os.path.exists(actions_path):
        with open(actions_path) as f:
            actions = [json.loads(line) for line in f if line.strip()]
        print(f"\n  Actions logged: {len(actions)}")

        # Analyze actions
        action_types = {}
        agents_active = set()
        posts = []
        for a in actions:
            at = a.get('action_type', 'unknown')
            action_types[at] = action_types.get(at, 0) + 1
            agents_active.add(a.get('agent_name', '?'))
            if at == 'CREATE_POST':
                content = a.get('action_args', {}).get('content', '')
                posts.append({
                    'agent': a.get('agent_name', '?'),
                    'content': content[:200],
                    'round': a.get('round_num', '?'),
                })

        print(f"  Agents active: {len(agents_active)}")
        print(f"  Action breakdown:")
        for at, count in sorted(action_types.items(), key=lambda x: -x[1]):
            print(f"    {at}: {count}")

        print(f"\n  Sample posts:")
        for p in posts[:5]:
            print(f"    [R{p['round']}] {p['agent']}: {p['content'][:150]}")

        save_json('06_action_analysis', {
            'total_actions': len(actions),
            'agents_active': list(agents_active),
            'action_types': action_types,
            'sample_posts': posts[:10],
        })
    else:
        print(f"  No actions file found at {actions_path}")
        # Check if actions are in a different location
        for root, dirs, files in os.walk(sim_dir):
            for f in files:
                if f.endswith('.jsonl') or f.endswith('.json'):
                    fpath = os.path.join(root, f)
                    size = os.path.getsize(fpath)
                    print(f"    Found: {fpath} ({size} bytes)")

    return elapsed


def main():
    print(f"\n{'#'*60}")
    print(f"  MiroShark Pipeline Test — Phases 5-6")
    print(f"  Model: {Config.LLM_MODEL_NAME}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Load previous graph stats
    stats_path = os.path.join(OUT_DIR, '03_graph_stats.json')
    if not os.path.exists(stats_path):
        print("ERROR: Run test_full_pipeline.py first to build the graph.")
        sys.exit(1)

    with open(stats_path) as f:
        graph_stats = json.load(f)
    graph_id = graph_stats['graph_id']
    print(f"  Reusing graph: {graph_id} ({graph_stats['node_count']} nodes, {graph_stats['edge_count']} edges)")

    # Load document text
    text_path = os.path.join(OUT_DIR, '01_parsed_text.txt')
    with open(text_path) as f:
        document_text = f.read()

    total_t0 = time.time()

    # Phase 5: Config generation
    config, storage = phase5_config(graph_id, document_text)

    # Phase 6: 3-round simulation
    sim_time = phase6_simulation(config, storage, graph_id)

    total_elapsed = time.time() - total_t0
    banner("COMPLETE")
    print(f"  Total time: {total_elapsed:.1f}s")
    print(f"  Output dir: {OUT_DIR}")
    for f in sorted(os.listdir(OUT_DIR)):
        if f.startswith('05_') or f.startswith('06_'):
            size = os.path.getsize(os.path.join(OUT_DIR, f))
            print(f"    {f} ({size:,} bytes)")


if __name__ == '__main__':
    main()
