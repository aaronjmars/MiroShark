<div align="center">

<img src="./miroshark-banner.jpg" alt="MiroShark Logo" width="75%"/>

<em>A Simple and Universal Swarm Intelligence Engine, Predicting Anything — Run Locally or with Any Cloud API</em>

</div>

## What is this?

**MiroShark** is a multi-agent simulation engine: upload any document (press release, policy draft, financial report), and it generates hundreds of AI agents with unique personalities that simulate the public reaction on social media. Posts, arguments, opinion shifts — hour by hour.

MiroShark runs on **Neo4j** for the knowledge graph and any **OpenAI-compatible API** for LLM inference and embeddings — use local Ollama (no cloud needed) or cloud providers like OpenRouter, OpenAI, or Anthropic.

> All you need to do: upload seed materials and describe your prediction requirements in natural language.
> MiroShark will return: a detailed prediction report and a high-fidelity digital world you can deeply interact with.

## Screenshots

<div align="center">
<table>
<tr>
<td><img src="./screen1.png" alt="Screenshot 1" width="100%"/></td>
<td><img src="./screen2.png" alt="Screenshot 2" width="100%"/></td>
</tr>
<tr>
<td><img src="./screen3.png" alt="Screenshot 3" width="100%"/></td>
<td><img src="./screen4.png" alt="Screenshot 4" width="100%"/></td>
</tr>
<tr>
<td><img src="./screen5.png" alt="Screenshot 5" width="100%"/></td>
<td><img src="./screen6.png" alt="Screenshot 6" width="100%"/></td>
</tr>
</table>
</div>

## Workflow

1. **Graph Build** — Extracts entities (people, companies, events) and relationships from your document. Builds a knowledge graph with individual and group memory via Neo4j.
2. **Agent Setup** — Generates hundreds of agent personas, each with unique personality, opinion bias, reaction speed, influence level, and memory of past events.
3. **Simulation** — Agents interact on simulated social platforms: posting, replying, arguing, shifting opinions. The system tracks sentiment evolution, topic propagation, and influence dynamics in real time. Supports **pause, resume, and restart** — simulations survive interruptions.
4. **Report** — A ReportAgent analyzes the post-simulation environment, interviews a focus group of agents, searches the knowledge graph for evidence, and generates a structured analysis. Reports are cached and reused.
5. **Interaction** — Chat with any agent from the simulated world via **persona chat** or send **group questions** to multiple agents at once. Click any agent to view their full profile and simulation activity. The environment auto-restarts for interviews if needed.

## Quick Start

### Prerequisites

- Docker & Docker Compose (recommended), **or**
- Python 3.11+, Node.js 18+, Neo4j 5.15+
- Ollama (for local inference) **or** an OpenRouter/OpenAI API key (for cloud inference)

### Option A: Docker (easiest)

```bash
git clone https://github.com/aaronjmars/MiroShark.git
cd MiroShark

# Start all services (Neo4j, Ollama, MiroShark)
docker compose up -d

# Pull the required models into Ollama
docker exec miroshark-ollama ollama pull qwen2.5:32b
docker exec miroshark-ollama ollama pull nomic-embed-text
```

Open `http://localhost:3000` — that's it.

### Option B: Manual

**1. Start Neo4j**

```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/miroshark \
  neo4j:5.15-community
```

**2. Start Ollama & pull models**

```bash
ollama serve &
ollama pull qwen2.5:32b      # LLM (or qwen2.5:14b for less VRAM)
ollama pull nomic-embed-text  # Embeddings (768d)
```

**3. Configure & run**

```bash
cp .env.example .env
# Edit .env if your Neo4j/Ollama are on non-default ports

# Install all dependencies
npm run setup:all

# Start both frontend and backend
npm run dev
```

Open `http://localhost:3000`.

**Service addresses:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

## Configuration

All settings are in `.env` (copy from `.env.example`):

```bash
# LLM — points to local Ollama (OpenAI-compatible API)
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen2.5:32b

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=miroshark

# Embeddings — "ollama" or "openai" provider
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_API_KEY=
EMBEDDING_DIMENSIONS=768
```

Works with **any OpenAI-compatible API** — swap Ollama for OpenRouter, OpenAI, Claude, or any other provider by changing `LLM_BASE_URL` and `LLM_API_KEY`.

**Example: OpenRouter (no local GPU needed)**

```bash
LLM_API_KEY=sk-or-v1-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=qwen/qwen-2.5-72b-instruct

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_BASE_URL=https://openrouter.ai/api
EMBEDDING_API_KEY=sk-or-v1-your-key
EMBEDDING_DIMENSIONS=768
```

## Architecture

```
┌─────────────────────────────────────────┐
│              Flask API                   │
│  graph.py  simulation.py  report.py     │
└──────────────┬──────────────────────────┘
               │ app.extensions['neo4j_storage']
┌──────────────▼──────────────────────────┐
│           Service Layer                  │
│  EntityReader  GraphToolsService         │
│  GraphMemoryUpdater  ReportAgent         │
└──────────────┬──────────────────────────┘
               │ storage: GraphStorage
┌──────────────▼──────────────────────────┐
│         GraphStorage (abstract)          │
│              │                            │
│    ┌─────────▼─────────┐                │
│    │   Neo4jStorage     │                │
│    │  ┌───────────────┐ │                │
│    │  │ EmbeddingService│ ← Ollama/OpenAI │
│    │  │ NERExtractor   │ ← Ollama LLM   │
│    │  │ SearchService  │ ← Hybrid search │
│    │  └───────────────┘ │                │
│    └───────────────────┘                │
└─────────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │  Neo4j CE   │
        │  5.15       │
        └─────────────┘
```

**Key design decisions:**

- `GraphStorage` is an abstract interface — swap Neo4j for any other graph DB by implementing one class
- `EmbeddingService` supports both Ollama (`/api/embed`) and OpenAI-compatible (`/v1/embeddings`) providers
- Dependency injection via Flask `app.extensions` — no global singletons
- Hybrid search: 0.7 × vector similarity + 0.3 × BM25 keyword search
- Simulation supports pause/resume/restart with action log persistence
- Auto-restart environment for interviews when simulation is not running
- All original simulation tools (InsightForge, Panorama, Agent Interviews) preserved

## Hardware Requirements

**Local mode (Ollama):**

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 16 GB | 32 GB |
| VRAM (GPU) | 10 GB (14b model) | 24 GB (32b model) |
| Disk | 20 GB | 50 GB |
| CPU | 4 cores | 8+ cores |

CPU-only mode works but is significantly slower for LLM inference. For lighter setups, use `qwen2.5:14b` or `qwen2.5:7b`.

**Cloud mode (OpenRouter/OpenAI):** No GPU required — just Neo4j and an API key. Any machine with 4 GB RAM can run the frontend + backend.

## Use Cases

- **PR crisis testing** — simulate the public reaction to a press release before publishing
- **Trading signal generation** — feed financial news and observe simulated market sentiment
- **Policy impact analysis** — test draft regulations against simulated public response
- **Creative experiments** — feed a novel with a lost ending; the agents write a narratively consistent conclusion

## License

AGPL-3.0 — same as the original MiroFish project. See [LICENSE](./LICENSE).

## Credits & Acknowledgments

Built on top of [MiroFish](https://github.com/666ghj/MiroFish) by [666ghj](https://github.com/666ghj), originally supported by [Shanda Group](https://www.shanda.com/).

The local Neo4j + Ollama storage layer (replacing Zep Cloud) was adapted from [MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline) by [nikmcfly](https://github.com/nikmcfly). Their work on making MiroFish fully local — including the `GraphStorage` abstraction, Neo4j schema, embedding service, NER extractor, hybrid search, and the translated service layer — was the foundation for MiroShark's offline capabilities.

MiroShark's simulation engine is powered by **[OASIS](https://github.com/camel-ai/oasis)** from the CAMEL-AI team.
