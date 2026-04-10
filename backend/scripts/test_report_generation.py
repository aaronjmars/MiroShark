#!/usr/bin/env python3
"""
Test report generation on the interconnected simulation results.

Uses the graph + simulation data from the previous test run.
"""

import json
import os
import sys
import time
from datetime import datetime

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, '..', '.env'))

OUT_DIR = os.path.join(_backend_dir, 'pipeline_test_output')

SIMULATION_REQUIREMENT = (
    "Simulate public reaction on Twitter and Reddit to this article. "
    "Focus on: community reactions, discussion threads, and how different "
    "user segments respond to the content."
)


def banner(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    print(f"\n{'#'*60}")
    print(f"  Report Generation Test")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    # Load graph ID from previous run
    with open(os.path.join(OUT_DIR, '03_graph_stats.json')) as f:
        graph_stats = json.load(f)
    graph_id = graph_stats['graph_id']
    print(f"  Graph: {graph_id} ({graph_stats['node_count']} nodes, {graph_stats['edge_count']} edges)")

    simulation_id = "sim_interconnected"
    print(f"  Simulation: {simulation_id}")

    # ── Initialize services ──
    banner("SETUP")

    from app.storage.neo4j_storage import Neo4jStorage
    from app.services.graph_tools import GraphToolsService
    from app.services.report_agent import ReportAgent

    storage = Neo4jStorage()
    graph_tools = GraphToolsService(storage=storage)

    agent = ReportAgent(
        graph_id=graph_id,
        simulation_id=simulation_id,
        simulation_requirement=SIMULATION_REQUIREMENT,
        graph_tools=graph_tools,
    )
    print("  ReportAgent initialized")

    # ── Generate report ──
    banner("GENERATING REPORT")

    def progress(stage, pct, msg):
        print(f"    [{stage}] {pct}% — {msg}")

    t0 = time.time()
    try:
        report = agent.generate_report(
            progress_callback=progress,
            report_id="test_report_001",
        )
        elapsed = time.time() - t0

        banner("REPORT GENERATED")
        print(f"  Time: {elapsed:.1f}s")
        print(f"  Status: {report.status}")
        print(f"  Sections: {len(report.sections)}")

        for i, section in enumerate(report.sections):
            title = section.get('title', section.get('section_title', f'Section {i+1}'))
            content = section.get('content', section.get('section_content', ''))
            print(f"\n  --- Section {i+1}: {title} ---")
            # Print first 500 chars of each section
            print(f"  {content[:500]}")
            if len(content) > 500:
                print(f"  ... ({len(content)} chars total)")

        # Check for full report file
        report_dir = os.path.join(_backend_dir, 'uploads', 'reports', 'test_report_001')
        full_report_path = os.path.join(report_dir, 'full_report.md')
        if os.path.exists(full_report_path):
            with open(full_report_path) as f:
                full_text = f.read()
            print(f"\n  Full report: {len(full_text)} chars")
            # Save a copy
            copy_path = os.path.join(OUT_DIR, '08_report.md')
            with open(copy_path, 'w') as f:
                f.write(full_text)
            print(f"  Saved to: {copy_path}")

        # Check agent log
        log_path = os.path.join(report_dir, 'agent_log.jsonl')
        if os.path.exists(log_path):
            with open(log_path) as f:
                log_lines = [json.loads(l) for l in f if l.strip()]
            print(f"\n  Agent log: {len(log_lines)} entries")
            tool_calls = [l for l in log_lines if l.get('type') == 'tool_call']
            tool_types = {}
            for tc in tool_calls:
                name = tc.get('tool_name', 'unknown')
                tool_types[name] = tool_types.get(name, 0) + 1
            print(f"  Tool calls: {len(tool_calls)}")
            for name, count in sorted(tool_types.items(), key=lambda x: -x[1]):
                print(f"    {name}: {count}")

            # Check for interview failures
            interview_calls = [l for l in log_lines if 'interview' in str(l.get('tool_name', '')).lower()]
            interview_errors = [l for l in log_lines if 'interview' in str(l.get('message', '')).lower() and 'fail' in str(l.get('message', '')).lower()]
            if interview_calls:
                print(f"\n  Interview calls: {len(interview_calls)}")
            if interview_errors:
                print(f"  Interview FAILURES: {len(interview_errors)}")
                for ie in interview_errors[:3]:
                    print(f"    {ie.get('message', '')[:150]}")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n  FAILED after {elapsed:.1f}s: {e}")
        import traceback
        traceback.print_exc()

        # Check partial output
        report_dir = os.path.join(_backend_dir, 'uploads', 'reports', 'test_report_001')
        if os.path.exists(report_dir):
            print(f"\n  Partial output in: {report_dir}")
            for f in os.listdir(report_dir):
                size = os.path.getsize(os.path.join(report_dir, f))
                print(f"    {f} ({size:,} bytes)")

    banner("DONE")


if __name__ == '__main__':
    main()
