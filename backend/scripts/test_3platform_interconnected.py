#!/usr/bin/env python3
"""
Test 2 platforms interconnected: Twitter + Reddit.

Validates:
- Both platforms run simultaneously
- Round memory: agents see cross-platform history
- Cross-platform digest: agents see their own activity on other platforms
- 8 rounds to allow belief drift + memory compaction
"""

import json
import os
import sys
import time
import csv
from datetime import datetime

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
sys.path.insert(0, _scripts_dir)
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, '..', '.env'))

OUT_DIR = os.path.join(_backend_dir, 'pipeline_test_output')
SIM_DIR = os.path.join(OUT_DIR, 'sim_interconnected')

SIMULATION_REQUIREMENT = (
    "Simulate public reaction on Twitter and Reddit to this article. "
    "Focus on: community reactions, discussion threads, and how different "
    "user segments respond to the content."
)


def banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def setup():
    banner("SETUP")

    for d in ['twitter', 'reddit']:
        os.makedirs(os.path.join(SIM_DIR, d), exist_ok=True)

    # Load existing outputs
    with open(os.path.join(OUT_DIR, '04_profiles.json')) as f:
        phase4_profiles = json.load(f)
    with open(os.path.join(OUT_DIR, '05_simulation_config.json')) as f:
        config = json.load(f)

    profile_lookup = {p['name'].lower(): p for p in phase4_profiles}
    agent_configs = config.get('agent_configs', [])

    # ── Override config ──
    config['time_config']['off_peak_activity_multiplier'] = 1.0
    config['time_config']['morning_activity_multiplier'] = 1.0
    config['time_config']['work_activity_multiplier'] = 1.0
    config['time_config']['peak_activity_multiplier'] = 1.0
    config['time_config']['agents_per_hour_min'] = len(agent_configs)
    config['time_config']['agents_per_hour_max'] = len(agent_configs)
    config['simulation_requirement'] = SIMULATION_REQUIREMENT

    for ac in agent_configs:
        ac['activity_level'] = 0.8  # not 1.0 — let some DO_NOTHING happen
        ac['active_hours'] = list(range(0, 24))

    # ── Reddit profiles ──
    reddit_profiles = []
    for i, ac in enumerate(agent_configs):
        name = ac.get('entity_name', f'Agent_{i}')
        p4 = profile_lookup.get(name.lower(), {})
        reddit_profiles.append({
            "user_id": i + 1, "username": p4.get('user_name', name.lower().replace(' ', '_')),
            "name": name, "bio": p4.get('bio', ''), "persona": p4.get('persona', ''),
            "karma": p4.get('karma', 1000), "age": p4.get('age', 30),
            "gender": p4.get('gender', 'other'), "mbti": p4.get('mbti', 'INTJ'),
            "country": p4.get('country', 'US'), "profession": p4.get('profession', ''),
            "interested_topics": p4.get('interested_topics', []), "created_at": "2024-01-01",
        })
    with open(os.path.join(SIM_DIR, 'reddit_profiles.json'), 'w') as f:
        json.dump(reddit_profiles, f, ensure_ascii=False, indent=2)

    # ── Twitter profiles ──
    tw_path = os.path.join(SIM_DIR, 'twitter_profiles.csv')
    with open(tw_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['user_id', 'name', 'username', 'user_char', 'description'])
        writer.writeheader()
        for i, ac in enumerate(agent_configs):
            name = ac.get('entity_name', f'Agent_{i}')
            p4 = profile_lookup.get(name.lower(), {})
            bio = p4.get('bio', '')
            persona = p4.get('persona', '')
            writer.writerow({
                'user_id': i + 1, 'name': name,
                'username': p4.get('user_name', name.lower().replace(' ', '_')),
                'user_char': f"{bio} {persona}".replace('\n', ' '),
                'description': bio.replace('\n', ' '),
            })

    # ── Save config ──
    config_path = os.path.join(SIM_DIR, 'simulation_config.json')
    with open(config_path, 'w') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"  Agents: {len(agent_configs)}")
    print(f"  Platforms: Twitter + Reddit")
    print(f"  Rounds: 8")
    return config_path


def run_simulation(config_path):
    banner("SIMULATION: 8 rounds, Twitter + Reddit, cross-platform ON")

    import subprocess
    cmd = [
        sys.executable, os.path.join(_scripts_dir, 'run_parallel_simulation.py'),
        '--config', config_path,
        '--max-rounds', '8',
        '--no-wait',
        '--cross-platform',
    ]

    t0 = time.time()
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=_backend_dir,
    )

    for line in proc.stdout:
        line = line.rstrip()
        if any(k in line for k in [
            'Sync]', 'Round ', 'complete', 'Error', 'FAILED',
            'Seeded', 'Market:', 'Published', 'Belief', 'Compacted',
            'Bridge', 'Memory', 'Trajectory',
        ]):
            # Skip massive persona dumps
            if len(line) < 200:
                print(f"    {line}")

    proc.wait()
    elapsed = time.time() - t0
    print(f"\n  Exit: {proc.returncode}, Time: {elapsed:.0f}s")
    return elapsed


def analyze():
    banner("ANALYSIS: Cross-platform interconnections")

    # ── Per-platform action breakdown ──
    for platform in ['twitter', 'reddit']:
        path = os.path.join(SIM_DIR, platform, 'actions.jsonl')
        if not os.path.exists(path):
            print(f"\n  [{platform.upper()}] No actions file")
            continue

        with open(path) as f:
            all_lines = [json.loads(l) for l in f if l.strip()]
        actions = [a for a in all_lines if 'action_type' in a]

        from collections import Counter
        types = Counter(a['action_type'] for a in actions)

        do_nothing = types.get('DO_NOTHING', 0) + types.get('do_nothing', 0)
        total = len(actions)
        dn_pct = f"{do_nothing/total*100:.0f}%" if total > 0 else "N/A"

        print(f"\n  [{platform.upper()}] {total} actions (DO_NOTHING: {do_nothing} = {dn_pct})")
        for t, c in types.most_common(8):
            print(f"    {t}: {c}")

        # Sample posts
        posts = [a for a in actions if a.get('action_type') in ('CREATE_POST', 'create_post')]
        if posts:
            print(f"  Posts ({len(posts)}):")
            for p in posts[:3]:
                agent = p.get('agent_name', '?')
                content = p.get('action_args', {}).get('content', '')[:140]
                print(f"    [{agent}] {content}")

    # ── Cross-platform evidence ──
    banner("CROSS-PLATFORM INTERCONNECTION CHECK")

    # Check if social posts reference market prices
    for platform in ['twitter', 'reddit']:
        path = os.path.join(SIM_DIR, platform, 'actions.jsonl')
        if not os.path.exists(path):
            continue
        with open(path) as f:
            actions = [json.loads(l) for l in f if l.strip()]
        posts = [a for a in actions if a.get('action_type') in ('CREATE_POST', 'CREATE_COMMENT', 'QUOTE_POST')]
        cross_refs = [p for p in posts if any(kw in (p.get('action_args', {}).get('content', '') or '').lower()
                      for kw in ['twitter', 'reddit', 'social media', 'trending', 'community'])]
        print(f"  [{platform.upper()}] {len(cross_refs)}/{len(posts)} posts reference cross-platform activity")
        for cr in cross_refs[:3]:
            content = cr.get('action_args', {}).get('content', '')[:150]
            print(f"    [{cr.get('agent_name', '?')}] {content}")

    # Check round memory file
    trajectory = os.path.join(SIM_DIR, 'trajectory.json')
    if os.path.exists(trajectory):
        with open(trajectory) as f:
            traj = json.load(f)
        print(f"\n  [BELIEF TRACKING]")
        print(f"    Topics: {traj.get('topics', [])}")
        print(f"    Rounds tracked: {traj.get('total_rounds', 0)}")
        convergence = traj.get('opinion_convergence', {})
        for topic, val in convergence.items():
            label = "CONVERGED" if val > 0.1 else "POLARIZED" if val < -0.1 else "STABLE"
            print(f"    {topic}: {label} ({val:+.2f})")
        turning = traj.get('turning_points', [])
        if turning:
            print(f"    Turning points: {len(turning)}")
            for tp in turning[:3]:
                print(f"      Round {tp['round']}: Agent_{tp['agent_id']} shifted {tp['direction']} on {tp['topic']} (delta: {tp['delta']:+.3f})")


def main():
    print(f"\n{'#'*60}")
    print(f"  3-Platform Interconnected Simulation Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    config_path = setup()
    elapsed = run_simulation(config_path)
    analyze()

    banner(f"DONE — {elapsed:.0f}s total")


if __name__ == '__main__':
    main()
