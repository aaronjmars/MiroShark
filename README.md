<div align="center">
<pre>
 ██████╗ ██████╗  ██████╗ ███████╗██████╗ ███████╗ ██████╗████████╗
 ██╔══██╗██╔══██╗██╔═══██╗██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝
 ██████╔╝██████╔╝██║   ██║███████╗██████╔╝█████╗  ██║        ██║
 ██╔═══╝ ██╔══██╗██║   ██║╚════██║██╔═══╝ ██╔══╝  ██║        ██║
 ██║     ██║  ██║╚██████╔╝███████║██║     ███████╗╚██████╗   ██║
 ╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝
     S  I  M
</pre>

**B2B Cold Email Variant Tester**
Test your email copy against AI personas before hitting send.

</div>

---

## What It Does

prospect-sim runs your B2B cold email variants against synthetic decision-maker personas derived from your ICP. It tells you which variant gets opened, which gets a reply, and — crucially — **where each one loses the prospect**.

Three phases:

1. **Graph Build** — Uploads your ICP file (MD/TXT/PDF) and builds a Neo4j knowledge graph of prospect personas. Cached after first run (~5-10 min once, then ~20 sec).
2. **Simulation** — Each email variant runs against multiple rounds of AI personas. Agents decide whether to open, reply, or drop out at each funnel stage.
3. **Ranking** — A ReACT agent analyzes all simulations and produces a ranked result: winner, scores per variant, and dropout point (subject line / opening / body / CTA).

Two interfaces — pick one:

- **`prospect-sim`** — Agent-friendly CLI. Non-interactive, `--quiet` JSON output, scriptable, pipeable.
- **`prospect-sim-tui`** — Human-friendly interactive REPL with live dashboard, orange branding, Hermes-style UX.

---

## How It Works

### The Complete Pipeline

```mermaid
flowchart LR
    A([📄 ICP file\nicp.md]) --> B
    C([📋 Variants\nvariants.json]) --> E

    subgraph PHASE1 ["① GRAPH BUILD  (~5-10 min, cached after first run)"]
        B[Upload ICP] --> D[LLM: Generate\nOntology]
        D --> E2[LLM: Extract entities\n& relationships per chunk]
        E2 --> F[(Neo4j\nKnowledge Graph)]
        F --> G[💾 Cache\nproject_id]
    end

    subgraph PHASE2 ["② SIMULATION  (~2-8 min)"]
        E[Load Variants] --> H[Spawn AI Personas\nfrom graph nodes]
        H --> I[Round 1…N\nPersona reads email\nOpen / Read / Reply / Dropout]
        I --> J[Record dropout\npoint per variant]
    end

    subgraph PHASE3 ["③ RANKING  (~1-2 min)"]
        J --> K[ReACT Report Agent\nanalyzes all rounds]
        K --> L([🏆 Ranked results\nwinner + dropout map])
    end

    PHASE1 --> PHASE2
    PHASE2 --> PHASE3
    G -.->|next run: skip build| PHASE2
```

---

### Phase 1 — ICP to Knowledge Graph

Your ICP document is transformed into a graph of interconnected personas. The LLM first designs the ontology (what *kinds* of entities matter for your simulation), then extracts every entity and relationship from the text.

```mermaid
flowchart TD
    A([📄 icp.md / .txt / .pdf]) --> B[Text extraction\n& chunking]

    B --> C["LLM: Ontology generation\n(Smart model)\n──────────────────\nDefines entity types:\n• HR Director\n• Company\n• Pain Point\n• Competitor\n• …\n\nDefines relationships:\n• WORKS_AT\n• HAS_PAIN\n• COMPETES_WITH\n• …"]

    C --> D["LLM: NER extraction\n(fast model, per chunk)\n──────────────────\nExtracts entities +\nrelationships from\neach text chunk"]

    D --> E[(Neo4j\nKnowledge Graph\n──────────────\nnodes: personas\nedges: relationships\nvectors: embeddings)]

    E --> F["LLM: Persona generation\n──────────────────\nEach entity → full\nAI persona with:\n• communication style\n• pain points\n• opinion stance\n• behavior patterns"]

    F --> G([project_id\ncached locally])

    style C fill:#2d2d2d,color:#FF6B35
    style D fill:#2d2d2d,color:#FF6B35
    style F fill:#2d2d2d,color:#FF6B35
    style E fill:#1a3a5c,color:#fff
```

---

### Phase 2 — Email Simulation Funnel

Each variant is tested through a 4-stage funnel across N simulation rounds. Every persona agent independently decides whether to proceed at each stage — or drop out.

```
                    ┌─────────────────────────────────────────┐
                    │           VARIANT: "Problem-led"         │
                    └────────────────────┬────────────────────┘
                                         │
                    ┌────────────────────▼────────────────────┐
                    │  STAGE 1 — SUBJECT LINE                  │
                    │  "Your onboarding is costing you hires"  │
                    │                                          │
                    │  100 personas see it                     │
                    │  78 open  ──────────────────────────►   │
                    │  22 delete without opening    ◄── ✗     │
                    └────────────────────┬────────────────────┘
                                         │ 78 opened
                    ┌────────────────────▼────────────────────┐
                    │  STAGE 2 — OPENING LINE                  │
                    │  "Most HR Directors we talk to lose..."  │
                    │                                          │
                    │  68 keep reading  ──────────────────►   │
                    │  10 lose interest here        ◄── ✗     │
                    └────────────────────┬────────────────────┘
                                         │ 68 reading
                    ┌────────────────────▼────────────────────┐
                    │  STAGE 3 — BODY                          │
                    │  "Skillia cuts onboarding from..."       │
                    │                                          │
                    │  57 reach CTA  ─────────────────────►   │
                    │  11 drop (too salesy / vague)  ◄── ✗    │
                    └────────────────────┬────────────────────┘
                                         │ 57 reach CTA
                    ┌────────────────────▼────────────────────┐
                    │  STAGE 4 — CTA                           │
                    │  "Worth a 15-min call this week?"        │
                    │                                          │
                    │  34 reply / book  ──────────────────►   │  ← reply_score
                    │  23 no action                 ◄── ✗     │
                    └─────────────────────────────────────────┘

Dropout point for this variant: "none" (most lost at subject or CTA, not a single bottleneck)
```

The **dropout point** tells you *where* to fix the copy — not just which variant won.

| Dropout value | Meaning |
|---|---|
| `subject_line` | Most personas never opened — rewrite the subject |
| `opening` | Opened but lost interest in line 1-2 — rewrite the hook |
| `body` | Got past the opening but disengaged mid-copy |
| `cta` | Read everything but didn't act — rewrite the ask |
| `none` | No single bottleneck — the copy performs consistently |

---

### Phase 3 — ReACT Ranking Report

After all simulations complete, a ReACT agent searches the graph and simulation data to produce a ranked analysis. It doesn't just count opens — it reasons about *why* personas responded the way they did.

```mermaid
flowchart LR
    A[Simulation results\nfrom all variants] --> B

    subgraph REACT ["ReACT Agent loop"]
        B[Plan: what sections\nshould this report cover?] --> C
        C[Tool: search graph\nfor persona context] --> D
        D[Tool: analyze\nbelief trajectories] --> E
        E[Tool: query\nsimulation feed] --> F
        F{Enough evidence?}
        F -- no --> C
        F -- yes --> G[Write section]
        G --> H{More sections?}
        H -- yes --> C
        H -- no --> I
    end

    I[Ranked results\n+ dropout map\n+ winner analysis] --> J([Output to CLI / TUI])
```

---

### Caching — First Run vs. Subsequent Runs

The graph build runs once per ICP file. After that, the same graph is reused for every test.

```mermaid
flowchart TD
    A([prospect-sim run\n--icp icp.md\n--variants variants.json]) --> B

    B[SHA256 hash\nof icp.md] --> C{Cache hit?\n~/.prospect-sim/cache.json}

    C -- "✓ hit" --> D[Verify project\nstill exists on backend]
    D -- "✓ exists" --> E["⚡ Reuse project_id\n~20 seconds"]
    D -- "✗ deleted" --> G

    C -- "✗ miss" --> G[Build graph\n~5-10 min]
    G --> H[Save project_id\nto cache]
    H --> E

    E --> I[Run simulations\nand generate report]
```

---

### System Architecture

```mermaid
flowchart TB
    subgraph CLIENTS ["Client Layer"]
        CLI["🖥️  prospect-sim\nAgent CLI\n(Typer, non-interactive)"]
        TUI["🎛️  prospect-sim-tui\nHuman TUI\n(prompt_toolkit + Rich)"]
    end

    subgraph BACKEND ["Backend  :5001  (Flask)"]
        direction TB
        G["/api/graph/*\nICP upload\nOntology + NER\nGraph build"]
        S["/api/simulation/*\nVariant test\nPrepare + Start\nPoll status"]
        R["/api/report/*\nReACT report\nPoll + Fetch"]
        CFG["/api/settings\nLLM config\nNeo4j config\n(live, no restart)"]
    end

    subgraph INFRA ["Infrastructure"]
        NEO4J[("Neo4j\nKnowledge Graph\npersonas + relationships\nvector embeddings")]
        LLM["LLM\nOntology · NER · Personas\nSimulation · Reports\n(OpenRouter / Ollama / etc.)"]
        CACHE["~/.prospect-sim/\ncache.json\nconfig.json"]
    end

    CLI -->|HTTP JSON| BACKEND
    TUI -->|HTTP JSON| BACKEND
    CLI <-->|read/write| CACHE
    TUI <-->|read/write| CACHE

    G <--> NEO4J
    S <--> NEO4J
    R <--> NEO4J
    G <--> LLM
    S <--> LLM
    R <--> LLM

    style CLI fill:#2d1a00,color:#FF6B35
    style TUI fill:#2d1a00,color:#FF6B35
    style NEO4J fill:#1a3a5c,color:#fff
    style LLM fill:#1a2d1a,color:#90ee90
```

---

## Installation

**Prerequisites:**
- Python 3.11+
- The prospect-sim backend running locally or remotely (see [Backend Setup](#backend-setup))

```bash
# Clone the repo
git clone https://github.com/Catafal/prospect-sim
cd prospect-sim/backend

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

This registers two commands: `prospect-sim` and `prospect-sim-tui`.

---

## Quick Start

### 1. Prepare your files

**ICP file** (`icp.md`) — describe your ideal customer:

```markdown
# ICP: HR Directors at Series B+ SaaS

## Role
Head of People or HR Director at B2B SaaS companies (100-500 employees).
Responsible for talent acquisition, retention, and performance management.

## Pain Points
- Manual onboarding takes 3+ weeks...
- Employee engagement scores declining post-COVID...

## Context
Reports to CEO or COO. Budget authority for $50k-$200k/year on HR tech.
```

**Variants file** (`variants.json`) — up to 6 email variants:

```json
[
  {
    "id": 1,
    "label": "Problem-led",
    "hook_type": "problem",
    "subject_line": "Your onboarding is costing you hires",
    "opening": "Most HR Directors we talk to lose 2-3 offers a month to slow onboarding...",
    "body": "Skillia cuts onboarding from 3 weeks to 3 days with AI micro-learning paths...",
    "cta": "Worth a 15-min call this week?"
  },
  {
    "id": 2,
    "label": "Social-proof-led",
    "hook_type": "social_proof",
    "subject_line": "How Typeform's HR team cut onboarding 70%",
    "opening": "Typeform's HR Director was dealing with the same problem you likely are...",
    "body": "They deployed Skillia across 200 new hires last quarter...",
    "cta": "I can show you exactly what they did — 15 min?"
  }
]
```

### 2. Run

```bash
# Full test — builds graph, simulates, ranks
prospect-sim run --icp icp.md --variants variants.json

# Preview what would happen, without running
prospect-sim run --icp icp.md --variants variants.json --dry-run

# CI/CD — clean JSON output, no prompts
prospect-sim run --icp icp.md --variants variants.json --quiet --yes | jq '.winner'

# More rounds for higher confidence
prospect-sim run --icp icp.md --variants variants.json --rounds 16 --parallel
```

### 3. Or use the interactive TUI

```bash
prospect-sim-tui
```

---

## Agent CLI Reference

### `prospect-sim run`

The main command. Does everything end-to-end.

```
prospect-sim run --icp <file> --variants <file> [OPTIONS]

Options:
  --icp <file>               ICP profile file (MD/TXT/PDF)              [required]
  --variants <file>          Variants JSON file (max 6 variants)        [required]
  --rounds <int>             Simulation rounds per variant              [default: 8]
  --parallel/--sequential    Run variants in parallel or sequentially   [default: sequential]
  --dry-run                  Show execution plan without running
  --quiet                    Output clean JSON only (pipeable)
  --yes, -y                  Skip confirmation prompts (unattended/CI)
  --api-url <url>            Backend URL                                [env: PROSPECT_SIM_API_URL]
```

**Output (default):**
```
Variant Ranking
┌─────┬─────────────────────┬────────────┬───────┬─────────┬──────────────┐
│ #   │ Variant             │ Hook       │ Opens │ Replies │ Main Dropout │
├─────┼─────────────────────┼────────────┼───────┼─────────┼──────────────┤
│ 👑1 │ Problem-led         │ problem    │ 78%   │ 34%     │ none         │
│   2 │ Social-proof-led    │ social_... │ 61%   │ 19%     │ opening      │
└─────┴─────────────────────┴────────────┴───────┴─────────┴──────────────┘

🏆 Winner: Problem-led
```

**Output (`--quiet`, pipeable JSON):**
```json
{
  "winner": "Problem-led",
  "ranking": [...],
  "failure_points": {"1": "none", "2": "opening"},
  "simulation_ids": ["sim_abc123", "sim_def456"]
}
```

**Machine-readable errors:**
```json
{"error": "backend_unavailable", "fix": "cd backend && uv run python run.py", "docs": "prospect-sim config set api-url <url>"}
```

---

### `prospect-sim project`

Manage ICP knowledge graph projects.

```bash
# List all cached projects (no backend needed)
prospect-sim project list
prospect-sim project list --quiet | jq '.[0].project_id'

# Build graph for an ICP file (cached after first run)
prospect-sim project build --icp icp.md
prospect-sim project build --icp icp.md --name "Skillia ICP v2"

# Show project details from backend
prospect-sim project show --project-id proj_abc123
```

---

### `prospect-sim variant`

Run simulations on an already-built project.

```bash
# Test variants against an existing cached project
prospect-sim variant test --project-id proj_abc123 --variants variants.json

# Or let it look up the project from ICP cache
prospect-sim variant test --icp icp.md --variants variants.json

# With options
prospect-sim variant test --icp icp.md --variants variants.json --rounds 12 --parallel --quiet
```

---

### `prospect-sim results`

Inspect simulation results.

```bash
# Show ranking for a simulation
prospect-sim results show --sim-id sim_abc123

# Status check only (no report generation)
prospect-sim results show --sim-id sim_abc123 --status
```

---

### `prospect-sim config`

Manage CLI configuration (stored in `~/.prospect-sim/config.json`).

```bash
# Show current config (CLI + backend live settings)
prospect-sim config show

# Set a value
prospect-sim config set api-url http://my-server:5001
prospect-sim config set default-rounds 12
prospect-sim config set default-parallel true

# Reset to defaults
prospect-sim config reset
```

**Config keys:**

| Key | Description | Default |
|---|---|---|
| `api-url` | Backend URL | `http://localhost:5001` |
| `default-rounds` | Rounds per variant | `8` |
| `default-parallel` | Parallel mode | `false` |

---

## Human TUI Reference

```bash
prospect-sim-tui [--api-url <url>]
```

Drops into an interactive REPL. First launch runs a 30-second setup wizard.

### Slash Commands

#### Simulation

| Command | Description |
|---|---|
| `/icp <file>` | Load an ICP file (tab-autocomplete). Builds graph if not cached — reuses in ~20s if cached. |
| `/add` | Interactive wizard to add an email variant to the session. |
| `/variants` | Show all current variants in a table. |
| `/rm <n>` | Remove variant by number. |
| `/run` | Simulate all variants. Shows live braille-spinner dashboard per variant. Prints ranking inline on completion. |
| `/why <n\|label>` | Explain why a variant ranked where it did. |
| `/graph` | Show the ICP knowledge graph structure — entity types, node/edge counts, breakdown bar chart. |
| `/graph open` | Same, plus opens the D3 force-directed visualization in your browser. |

#### Session

| Command | Description |
|---|---|
| `/rounds <n>` | Set rounds per variant (default: 8). |
| `/parallel` | Toggle parallel / sequential simulation mode. |
| `/history` | Show all cached ICP projects. |
| `/clear` | Clear all current variants. |
| `/new` | Reset session — clear ICP, variants, and results. |

#### Configuration

| Command | Description |
|---|---|
| `/config` | Show all settings (CLI keys + live backend settings). |
| `/config set <key> <value>` | Change a setting. Keys: `api-url`, `rounds`, `parallel`, `model`, `base-url`, `api-key`. |
| `/config test` | Fire a test call to the current LLM and report latency. |
| `/setup` | Re-run the setup wizard. |

**Config keys in TUI:**

| Key | Stored | Description |
|---|---|---|
| `api-url` | `~/.prospect-sim/config.json` | Backend URL |
| `rounds` | `~/.prospect-sim/config.json` | Default rounds |
| `parallel` | `~/.prospect-sim/config.json` | Parallel mode |
| `model` | Backend in-memory | LLM model name |
| `base-url` | Backend in-memory | LLM base URL (for Ollama) |
| `api-key` | Backend in-memory | LLM API key |

#### Other

| Command | Description |
|---|---|
| `/help` | Show command reference. |
| `/quit` | Exit. |

---

## ICP Graph Caching

The graph build (~5-10 min) runs once per unique ICP file. The SHA256 hash of the file is stored in `~/.prospect-sim/cache.json` alongside the `project_id`.

On subsequent runs — CLI or TUI — the cache is checked first:

```
/icp icp.md  →  [SHA256 match]  →  ⚡ reusing project proj_abc123  (~20s)
               [no match]      →  Building graph...  (~5-10 min)
```

The cache also validates the project still exists on the backend. If it was deleted, it rebuilds and re-caches automatically.

**Cache location:** `~/.prospect-sim/cache.json`

---

## Variants File Format

```json
[
  {
    "id": 1,                          // unique integer (required)
    "label": "Problem-led",           // display name (required)
    "hook_type": "problem",           // one of: problem, social_proof, insight, curiosity, value
    "subject_line": "...",            // email subject
    "opening": "...",                 // first 1-2 sentences
    "body": "...",                    // main copy
    "cta": "..."                      // call to action
  }
]
```

Max 6 variants per run. All fields except `id` and `label` are passed to the simulation as copy content — include whatever email elements you want tested.

---

## Backend Setup

prospect-sim talks to the Flask backend over HTTP. The backend handles LLM calls, Neo4j, and simulations.

```bash
cd backend
cp .env.example .env  # configure LLM + Neo4j
uv run python run.py  # starts on :5001
```

### One-Click Cloud Deploy

Deploy the backend to the cloud in under 3 minutes — no local setup required.

**Before you deploy, create:**
1. A free [Neo4j Aura](https://neo4j.com/cloud/aura-free/) instance — grab the `NEO4J_URI` (starts with `neo4j+s://`) and password.
2. An [OpenRouter](https://openrouter.ai/) API key — free credits on signup.

**Railway** (recommended — persistent storage, free trial):

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.app/new/template?template=https://github.com/Catafal/prospect-sim)

Set these environment variables in the Railway dashboard:

| Variable | Value |
|---|---|
| `LLM_API_KEY` | Your OpenRouter key (`sk-or-v1-...`) |
| `NEO4J_URI` | Your Aura URI (`neo4j+s://...`) |
| `NEO4J_PASSWORD` | Your Aura password |
| `EMBEDDING_API_KEY` | Same OpenRouter key |

Then point the CLI at your deployed URL:

```bash
prospect-sim config set api-url https://your-app.up.railway.app
```

---

### LLM Configuration

#### Cloud (OpenRouter) — no GPU needed

| Model | ID | Cost/sim | Notes |
|---|---|---|---|
| **Qwen3 235B A22B** ⭐ | `qwen/qwen3-235b-a22b-2507` | ~$0.30 | Best overall |
| GPT-5 Nano | `openai/gpt-5-nano` | ~$0.41 | Budget option |
| Gemini 2.5 Flash Lite | `google/gemini-2.5-flash-lite` | ~$0.58 | Good alt |
| DeepSeek V3.2 | `deepseek/deepseek-v3.2` | ~$1.11 | Stronger reasoning |

```bash
# .env
LLM_API_KEY=sk-or-v1-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL_NAME=qwen/qwen3-235b-a22b-2507

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_BASE_URL=https://openrouter.ai/api
EMBEDDING_API_KEY=sk-or-v1-your-key
EMBEDDING_DIMENSIONS=768
```

#### Local (Ollama) — no API key needed

> **Context override required.** Ollama defaults to 4096 tokens, but prompts need 10-30k. Create a custom Modelfile:
>
> ```bash
> printf 'FROM qwen3:14b\nPARAMETER num_ctx 32768' > Modelfile
> ollama create prospect-sim-llm -f Modelfile
> ```

| Model | VRAM | Speed | Notes |
|---|---|---|---|
| `qwen3.5:27b` | 20 GB+ | ~40 t/s | Best quality |
| `qwen3.5:35b-a3b` *(MoE)* | 16 GB | ~112 t/s | Fastest |
| `qwen3:14b` | 12 GB | ~60 t/s | Solid balance |
| `qwen3:8b` | 8 GB | ~42 t/s | Minimum viable |

**Hardware quick-pick:**

| Setup | Model |
|---|---|
| RTX 3090/4090 or M2 Pro 32 GB+ | `qwen3.5:27b` |
| RTX 4080 / M2 Pro 16 GB | `qwen3.5:35b-a3b` |
| RTX 4070 / M1 Pro | `qwen3:14b` |
| 8 GB VRAM / laptop | `qwen3:8b` |

```bash
# .env for Ollama
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL_NAME=qwen3:14b

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_BASE_URL=http://localhost:11434
EMBEDDING_DIMENSIONS=768
```

**Tip:** Use a fast local model for simulation rounds (high-volume) and route only report generation to a cloud model with `SMART_MODEL_NAME`:

```bash
LLM_MODEL_NAME=qwen3:14b                     # bulk simulation work
SMART_MODEL_NAME=anthropic/claude-sonnet-4   # reports + ontology (via OpenRouter)
SMART_API_KEY=sk-or-v1-your-key
SMART_BASE_URL=https://openrouter.ai/api/v1
```

---

## Code Structure

```
prospect-sim/
├── backend/
│   ├── app/                         Flask API
│   │   ├── services/                Business logic
│   │   │   ├── ontology_generator.py
│   │   │   ├── oasis_profile_generator.py
│   │   │   └── report_agent.py
│   │   └── storage/
│   │       ├── neo4j_storage.py     Graph persistence
│   │       └── ner_extractor.py     Entity extraction
│   │
│   └── prospect_sim_cli/            CLI + TUI package
│       ├── main.py                  Typer root app
│       ├── client.py                HTTP client (ApiClient, ApiError)
│       ├── cache.py                 ICP cache + CLI config
│       ├── output.py                Rich tables, spinner, JSON printer
│       ├── commands/
│       │   ├── run.py               prospect-sim run
│       │   ├── project.py           prospect-sim project list/build/show
│       │   ├── variant.py           prospect-sim variant test
│       │   ├── results.py           prospect-sim results show
│       │   └── config_cmd.py        prospect-sim config
│       ├── tui.py                   Human TUI REPL
│       ├── tui_config.py            /config + /setup mixin
│       ├── tui_graph.py             /graph mixin
│       └── tui_constants.py         ORANGE, SPINNER, LOGO, SLASH_COMMANDS
│
└── frontend/                        Vue 3 web UI (optional)
    └── src/components/GraphPanel.vue  D3 force-directed graph viz
```

---

## Credits

Built on [MiroShark](https://github.com/aaronjmars/MiroShark) — multi-agent swarm simulation engine.
Simulation engine powered by [OASIS](https://github.com/camel-ai/oasis) (CAMEL-AI).
TUI design inspired by [Hermes Agent](https://github.com/nousresearch/hermes-agent) (NousResearch).

AGPL-3.0.
