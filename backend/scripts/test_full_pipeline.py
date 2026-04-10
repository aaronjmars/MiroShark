#!/usr/bin/env python3
"""
Full pipeline test — runs every phase with detailed logging.

Usage:
    cd backend
    .venv/bin/python scripts/test_full_pipeline.py

Phases:
    1. Parse PDF → text
    2. Generate ontology (LLM call #1)
    3. Build knowledge graph (LLM calls #2: NER per chunk)
    4. Generate agent profiles (LLM calls #3-4: web enrichment + persona)
    5. Generate simulation config (LLM calls #6-8: time + event + agent config)
    6. Run 3-round simulation (LLM calls #9-11: agent actions)

Each phase logs timing, prompts, and output quality.
"""

import json
import os
import sys
import time
from datetime import datetime

# Setup paths
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, '..'))
sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, '..', '.env'))

from app.config import Config
from app.utils.file_parser import FileParser
from app.services.text_processor import TextProcessor
from app.utils.llm_client import create_llm_client
from app.utils.logger import get_logger

logger = get_logger('pipeline_test')

# Output directory for logs
OUT_DIR = os.path.join(_backend_dir, 'pipeline_test_output')
os.makedirs(OUT_DIR, exist_ok=True)

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


# ── PDF path ──
PDF_PATH = os.path.join(_backend_dir, '..',
    'sample_article.pdf')

SIMULATION_REQUIREMENT = (
    "Simulate public reaction on Twitter and Reddit to this article. "
    "Focus on: community reactions, discussion threads, and how different "
    "user segments respond to the content."
)


def phase1_parse():
    banner("PHASE 1: Parse PDF")
    t0 = time.time()

    raw_text = FileParser.extract_text(PDF_PATH)
    clean_text = TextProcessor.preprocess_text(raw_text)

    elapsed = time.time() - t0
    print(f"  Raw text: {len(raw_text)} chars")
    print(f"  Clean text: {len(clean_text)} chars")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Preview: {clean_text[:300]}...")

    save_text('01_parsed_text', clean_text)
    return clean_text


def phase2_ontology(document_text):
    banner("PHASE 2: Generate Ontology")
    t0 = time.time()

    from app.services.ontology_generator import OntologyGenerator
    generator = OntologyGenerator()

    ontology = generator.generate(
        document_texts=[document_text],
        simulation_requirement=SIMULATION_REQUIREMENT,
    )

    elapsed = time.time() - t0
    entity_types = ontology.get('entity_types', [])
    edge_types = ontology.get('edge_types', [])

    print(f"  Entity types ({len(entity_types)}):")
    for et in entity_types:
        print(f"    - {et.get('name', et)}: {et.get('description', '')[:80]}")
    print(f"  Edge types ({len(edge_types)}):")
    for rt in edge_types:
        print(f"    - {rt.get('name', rt)}: {rt.get('description', '')[:80]}")
    print(f"  Time: {elapsed:.1f}s")

    save_json('02_ontology', ontology)
    return ontology


def phase3_graph(document_text, ontology):
    banner("PHASE 3: Build Knowledge Graph")
    t0 = time.time()

    from app.storage.neo4j_storage import Neo4jStorage
    from app.services.graph_builder import GraphBuilderService

    storage = Neo4jStorage()
    builder = GraphBuilderService(storage=storage)

    # Create graph
    graph_id = builder.create_graph(name="Pipeline Test")
    builder.set_ontology(graph_id, ontology)

    # Chunk text
    chunks = TextProcessor.split_text(document_text, chunk_size=500, overlap=50)
    # Limit to first 8 chunks for testing speed
    test_chunks = chunks[:8]
    print(f"  Total chunks: {len(chunks)}, testing with: {len(test_chunks)}")

    def progress(msg, ratio):
        print(f"    [{ratio*100:.0f}%] {msg}")

    episode_ids = builder.add_text_batches(
        graph_id, test_chunks, batch_size=3, progress_callback=progress
    )

    # Get graph stats
    graph_data = builder.get_graph_data(graph_id)

    elapsed = time.time() - t0
    print(f"  Nodes: {graph_data.get('node_count', 0)}")
    print(f"  Edges: {graph_data.get('edge_count', 0)}")
    print(f"  Entity types found: {graph_data.get('entity_types', [])}")
    print(f"  Episodes: {len(episode_ids)}")
    print(f"  Time: {elapsed:.1f}s ({elapsed/len(test_chunks):.1f}s per chunk)")

    # Save sample nodes
    nodes = graph_data.get('nodes', [])[:10]
    save_json('03_graph_sample_nodes', nodes)
    save_json('03_graph_stats', {
        'graph_id': graph_id,
        'node_count': graph_data.get('node_count', 0),
        'edge_count': graph_data.get('edge_count', 0),
        'entity_types': graph_data.get('entity_types', []),
        'chunks_processed': len(test_chunks),
        'time_seconds': elapsed,
    })

    return storage, graph_id, graph_data


def phase4_profiles(storage, graph_id, ontology):
    banner("PHASE 4: Generate Agent Profiles")
    t0 = time.time()

    from app.services.entity_reader import EntityReader
    from app.services.oasis_profile_generator import OasisProfileGenerator

    reader = EntityReader(storage)
    entity_types = [et.get('name', et) if isinstance(et, dict) else et
                    for et in ontology.get('entity_types', [])]

    filtered = reader.filter_defined_entities(
        graph_id=graph_id,
        defined_entity_types=entity_types,
        enrich_with_edges=True,
    )

    print(f"  Entities found: {filtered.filtered_count}")
    print(f"  Entity types: {list(filtered.entity_types)}")

    # Limit to 5 entities for testing
    test_entities = filtered.entities[:5]
    print(f"  Testing with {len(test_entities)} entities:")
    for e in test_entities:
        print(f"    - {e.name} ({e.get_entity_type()}): {(e.summary or '')[:80]}")

    generator = OasisProfileGenerator(
        storage=storage,
        graph_id=graph_id,
        simulation_requirement=SIMULATION_REQUIREMENT,
    )

    profiles = []
    for i, entity in enumerate(test_entities):
        pt0 = time.time()
        profile = generator.generate_profile_from_entity(entity, user_id=i+1)
        pt1 = time.time()

        profiles.append(profile)
        print(f"\n  [{i+1}/{len(test_entities)}] {profile.name} ({profile.source_entity_type}) — {pt1-pt0:.1f}s")
        print(f"    Bio: {profile.bio[:120]}...")
        print(f"    Persona: {profile.persona[:200]}...")
        print(f"    Age: {profile.age}, Gender: {profile.gender}, MBTI: {profile.mbti}")
        print(f"    Profession: {profile.profession}")
        print(f"    Topics: {profile.interested_topics}")
        print(f"    Risk tolerance: {profile.risk_tolerance}")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s ({elapsed/len(test_entities):.1f}s per profile)")

    profiles_data = [p.to_dict() for p in profiles]
    save_json('04_profiles', profiles_data)

    return profiles


def phase5_config(document_text, ontology, profiles):
    banner("PHASE 5: Generate Simulation Config")
    t0 = time.time()

    from app.services.simulation_config_generator import SimulationConfigGenerator

    # Build entity list from profiles
    entities = []
    for p in profiles:
        entities.append({
            'name': p.name,
            'type': p.source_entity_type or 'Entity',
            'summary': p.bio,
        })

    generator = SimulationConfigGenerator()

    def progress(step, total, msg):
        print(f"    [{step}/{total}] {msg}")

    result = generator.generate_config(
        simulation_requirement=SIMULATION_REQUIREMENT,
        document_text=document_text[:3000],
        entities=entities,
        progress_callback=progress,
    )

    elapsed = time.time() - t0
    config = result if isinstance(result, dict) else result.to_dict() if hasattr(result, 'to_dict') else {}

    print(f"\n  Time config:")
    tc = config.get('time_config', {})
    print(f"    Total hours: {tc.get('total_simulation_hours')}")
    print(f"    Minutes per round: {tc.get('minutes_per_round')}")

    print(f"  Agent configs: {len(config.get('agent_configs', []))}")
    for ac in config.get('agent_configs', [])[:3]:
        print(f"    - {ac.get('entity_name', '?')}: activity={ac.get('activity_level')}, "
              f"stance={ac.get('stance')}, sentiment={ac.get('sentiment_bias')}")

    print(f"  Event config:")
    ec = config.get('event_config', {})
    print(f"    Initial posts: {len(ec.get('initial_posts', []))}")
    for ip in ec.get('initial_posts', [])[:2]:
        print(f"      - {ip.get('poster_type', '?')}: {str(ip.get('content', ''))[:100]}")

    print(f"  Time: {elapsed:.1f}s")

    save_json('05_simulation_config', config)
    return config


def main():
    print(f"\n{'#'*60}")
    print(f"  MiroShark Full Pipeline Test")
    print(f"  PDF: {os.path.basename(PDF_PATH)}")
    print(f"  Requirement: {SIMULATION_REQUIREMENT[:80]}...")
    print(f"  Model: {Config.LLM_MODEL_NAME}")
    print(f"  Output: {OUT_DIR}")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*60}")

    total_t0 = time.time()

    # Phase 1: Parse PDF
    document_text = phase1_parse()

    # Phase 2: Generate Ontology
    ontology = phase2_ontology(document_text)

    # Phase 3: Build Graph (8 chunks)
    storage, graph_id, graph_data = phase3_graph(document_text, ontology)

    # Phase 4: Generate Profiles (5 entities)
    profiles = phase4_profiles(storage, graph_id, ontology)

    # Phase 5: Generate Config
    config = phase5_config(document_text, ontology, profiles)

    # Summary
    total_elapsed = time.time() - total_t0
    banner("PIPELINE COMPLETE")
    print(f"  Total time: {total_elapsed:.1f}s")
    print(f"  Output dir: {OUT_DIR}")
    print(f"  Files generated:")
    for f in sorted(os.listdir(OUT_DIR)):
        size = os.path.getsize(os.path.join(OUT_DIR, f))
        print(f"    {f} ({size:,} bytes)")


if __name__ == '__main__':
    main()
