<div align="center">

# ChaosGuard AI

### Autonomous Security Scanner & Chaos Engineering Platform

**Drop in a GitHub URL. Get back a full security audit, attack chain analysis, chaos resilience report, and auto-generated fix PRs — powered entirely by local LLMs.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?logo=ollama)](https://ollama.com)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](frontend/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2-6DB33F?logo=spring&logoColor=white)](gateway/)

---

**No API keys. No cloud. No data leaves your machine.**

</div>

<br>

## What is ChaosGuard?

ChaosGuard is a **self-hosted, AI-powered security platform** that scans any GitHub repository across four escalating tiers of depth — from rapid static analysis to full chaos engineering simulations. Every finding comes with an auto-generated code fix, a unified diff, and one-click PR creation.

It runs entirely on your machine using **Ollama** for local LLM inference, **ChromaDB** for RAG-powered code understanding, and a **Kafka-driven agent architecture** that scales from a single laptop to a cluster.

<br>

## Key Features

<table>
<tr>
<td width="50%">

### Multi-Tier Scanning
Four escalating scan tiers with increasing depth:

- **RECON** — Static analysis in seconds. Secret detection, dependency vulnerabilities, config issues, dangerous function calls
- **HUNTER** — LLM-powered vulnerability hunting with RAG context. Finds injection flaws, auth bypasses, business logic bugs
- **SIEGE** — Attack chain construction, chaos cascade simulation, compound failure analysis, pentest playbook generation
- **LIVE** — DAST probes against running targets (SQLi, IDOR, auth bypass, race conditions)

</td>
<td width="50%">

### AI-Powered Fix Generation
Every finding gets an auto-generated fix:

- **Template fixes** for known patterns (secrets, configs, dependencies)
- **LLM-generated patches** with original/fixed code diffs
- **Sandbox validation** — fixes are compiled and tested before surfacing
- **One-click PR creation** — branches, commits, and labels auto-generated
- **Self-validation** — LLM reviews its own fixes for correctness

</td>
</tr>
<tr>
<td width="50%">

### Chaos Engineering
Resilience analysis that goes beyond vulnerabilities:

- Identifies missing circuit breakers, retry logic, timeouts, health checks
- Simulates **compound failure cascades** across service boundaries
- Estimates blast radius and recovery time for each scenario
- Generates **LitmusChaos experiment specs** ready for Kubernetes
- Maps failure propagation paths through your dependency graph

</td>
<td width="50%">

### RAG-Powered Code Understanding
Every agent reasons over your actual codebase:

- Full repo indexing with **nomic-embed-text** embeddings
- **ChromaDB** vector store for semantic code search
- Agents retrieve relevant code context before analysis
- Cross-file correlation catches vulnerabilities that span modules
- Dependency graph extraction for impact analysis

</td>
</tr>
</table>

<br>

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js 15)                       │
│  Dashboard │ Findings │ Attack Chains │ Chaos │ Code │ Graph │ Fixes│
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST + WebSocket
┌──────────────────────────────▼──────────────────────────────────────┐
│                     Gateway (Spring Boot 3.2)                       │
│            API │ Scan Orchestration │ GitHub Integration             │
└──────┬───────────────┬────────────────┬─────────────────────────────┘
       │               │                │
   ┌───▼───┐    ┌──────▼──────┐   ┌─────▼─────┐
   │ Kafka │    │  PostgreSQL  │   │   Redis   │
   │ Events│    │   Findings   │   │  Cache +  │
   │       │    │   Fixes      │   │  Metrics  │
   └───┬───┘    └─────────────┘   └───────────┘
       │
  ┌────▼─────────────────────────────────────────────────┐
  │              Agent Workers (Python)                    │
  │                                                       │
  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐ │
  │  │  RECON  │  │  HUNTER  │  │  SIEGE   │  │ LIVE  │ │
  │  │ Worker  │  │  Worker  │  │  Worker  │  │Worker │ │
  │  └────┬────┘  └────┬─────┘  └────┬─────┘  └───┬───┘ │
  │       │            │             │             │      │
  │  ┌────▼────────────▼─────────────▼─────────────▼──┐  │
  │  │           Orchestrator + Fix Generator          │  │
  │  └────────────────────┬───────────────────────────┘  │
  │                       │                               │
  │  ┌────────────────────▼───────────────────────────┐  │
  │  │   Ollama (Local LLM)  │   ChromaDB (RAG)       │  │
  │  │   qwen2.5-coder:7b    │   nomic-embed-text     │  │
  │  │   llama3.1:8b          │   768-dim embeddings   │  │
  │  └────────────────────────────────────────────────┘  │
  └──────────────────────────────────────────────────────┘
```

**12 services**, one `docker compose up`. That's it.

<br>

## Quick Start

### Prerequisites

- **Docker Desktop** (4GB+ RAM allocated)
- **Ollama** installed ([ollama.com](https://ollama.com))
- **16GB+ RAM** recommended (24GB for concurrent SIEGE scans)

### 1. Clone & Configure

```bash
git clone https://github.com/Ayush1906saxena/ChaosGuard.git
cd ChaosGuard
cp .env.example .env
# Edit .env with your Postgres password (or keep defaults for local dev)
```

### 2. Start Ollama with Optimized Settings

```bash
# Pull required models
ollama pull qwen2.5-coder:7b
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Start with memory-optimized settings
OLLAMA_MAX_LOADED_MODELS=3 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 ollama serve
```

### 3. Launch Everything

```bash
# One command to rule them all
./start.sh

# Or manually:
docker compose up -d
```

### 4. Open the Dashboard

Navigate to **[http://localhost:3000](http://localhost:3000)**, paste a GitHub URL, select a tier, and hit scan.

<br>

## Scan Tiers

| Tier | Speed | What It Does | Agents |
|------|-------|-------------|--------|
| **RECON** | ~1 sec | Static analysis, secret detection, dependency audit, config review | Secret Scanner, Dependency Scanner, Config Auditor, SAST |
| **HUNTER** | ~8 min | LLM-powered vulnerability hunting with RAG code context | Vulnerability Hunter, Load Analyzer, Config Auditor, Chaos Architect |
| **SIEGE** | ~15 min | Attack chains, chaos simulation, compound failures, pentest playbooks | All Hunter agents + Attack Chain Constructor, Chaos Cascade Simulator, Exploit Analyst, Business Logic Analyzer |
| **LIVE** | Varies | Active DAST probes against a running target URL | SQLi Probe, IDOR Probe, Auth Bypass, Race Condition |

<br>

## UI Pages

| Page | Description |
|------|-------------|
| **Dashboard** | Start scans, view history, real-time progress via WebSocket |
| **Report** | Severity breakdown, category distribution, filterable findings table |
| **Attack Chains** | Multi-step attack path visualization with MITRE ATT&CK mapping |
| **Chaos Scenarios** | Blast radius charts, failure timelines, recovery estimates |
| **Code Explorer** | File tree with inline vulnerability highlighting and finding details |
| **Dependency Graph** | Interactive D3.js force-directed graph with risk-colored nodes |
| **Fixes** | AI-generated patches with diff viewer, one-click GitHub PR creation |
| **Pentest Playbook** | Step-by-step testing guide with cURL commands and expected behavior |

<br>

## MCP Server

ChaosGuard includes an **MCP (Model Context Protocol) server** that exposes scan data as tools for AI assistants like Claude:

```bash
# The MCP server starts automatically with docker compose
# Connect your AI assistant to http://localhost:5001
```

Available tools: `list_scans`, `get_scan`, `get_findings`, `get_attack_chains`, `get_chaos_scenarios`, `search_code`

<br>

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 15, React 19, Tailwind CSS, D3.js, WebSocket |
| **API Gateway** | Spring Boot 3.2, JPA/Hibernate, WebSocket (STOMP) |
| **Agents** | Python 3.12, asyncio, httpx |
| **LLM Inference** | Ollama (local), qwen2.5-coder:7b, llama3.1:8b |
| **Embeddings** | nomic-embed-text (768-dim) via Ollama |
| **Vector Store** | ChromaDB |
| **Message Broker** | Apache Kafka (KRaft mode) |
| **Database** | PostgreSQL 16 |
| **Cache** | Redis 7 |
| **Orchestration** | Docker Compose |

<br>

## Project Structure

```
ChaosGuard/
├── frontend/          # Next.js 15 dashboard
├── gateway/           # Spring Boot API gateway
├── agents/            # Python AI agent workers
│   ├── tier1_recon/   #   Static analysis agents
│   ├── tier2_hunter/  #   LLM-powered vulnerability hunters
│   ├── tier3_siege/   #   Attack chain & chaos simulation
│   ├── dast/          #   Live DAST probe agents
│   └── generators/    #   Fix generation & sandbox validation
├── indexer/           # Repo cloning, parsing, embedding
├── mcp-server/        # MCP protocol server for AI assistants
├── shared/            # Shared Python config & utilities
├── scripts/           # DB migrations, benchmarks
└── docker-compose.yml # Full stack orchestration
```

<br>

## Configuration

All configuration is in `.env`. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_CODE_MODEL` | `qwen2.5-coder:7b` | Model for code analysis and fix generation |
| `OLLAMA_REASONING_MODEL` | `llama3.1:8b` | Model for reasoning and attack chains |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model for RAG (768-dim) |
| `MAX_CONCURRENT_SCANS` | `3` | Parallel scan limit |
| `GITHUB_DEFAULT_TOKEN` | _(empty)_ | GitHub PAT for PR creation |

### Memory Optimization

For machines with limited RAM, set these before starting Ollama:

```bash
export OLLAMA_MAX_LOADED_MODELS=3    # Max models in RAM simultaneously
export OLLAMA_NUM_PARALLEL=1         # Single concurrent request per model
export OLLAMA_FLASH_ATTENTION=1      # Flash attention for lower memory usage
```

With these settings, ChaosGuard runs comfortably on **16GB RAM**.

<br>

## API Reference

Base URL: `http://localhost:8080/api/v1`

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/scans` | Create a new scan |
| `GET` | `/scans/{id}` | Get scan status |
| `GET` | `/scans/{id}/findings` | List findings (paginated, filterable) |
| `GET` | `/scans/{id}/fixes` | List generated fixes |
| `POST` | `/scans/{id}/fixes/create-pr` | Create GitHub PRs for fixes |
| `GET` | `/scans/{id}/attack-chains` | Get attack chains (SIEGE) |
| `GET` | `/scans/{id}/chaos-scenarios` | Get chaos scenarios |
| `GET` | `/scans/{id}/report` | Full scan report |
| `GET` | `/scans/{id}/dependency-graph` | Dependency graph data |
| `POST` | `/findings/{id}/feedback` | Submit finding feedback |

<br>

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

<br>

## License

MIT

<br>

---

<div align="center">

**If ChaosGuard helped you find a vulnerability, consider giving it a star.**

</div>
