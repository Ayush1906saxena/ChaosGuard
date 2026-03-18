#!/usr/bin/env bash
set -euo pipefail

# ─── ChaosGuard AI — One-command startup ────────────────────────────────────
# Usage: ./start.sh [--clean]
#   --clean   Wipe all volumes and rebuild from scratch

cd "$(dirname "$0")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║              ⚔️  ChaosGuard AI  ⚔️                          ║${NC}"
  echo -e "${CYAN}║     AI-Powered Security & Chaos Engineering Platform       ║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
  echo ""
}

log()  { echo -e "  ${GREEN}[✓]${NC} $1"; }
warn() { echo -e "  ${YELLOW}[!]${NC} $1"; }
err()  { echo -e "  ${RED}[✗]${NC} $1"; }
step() { echo -e "\n${BOLD}${CYAN}$1${NC}"; }

# ── Pre-flight checks ───────────────────────────────────────────────────────

banner

step "1/6  Pre-flight checks"

# Check Docker
if ! command -v docker &>/dev/null; then
  err "Docker is not installed. Please install Docker Desktop first."
  exit 1
fi

if ! docker info &>/dev/null; then
  warn "Docker daemon is not running. Attempting to start Docker Desktop..."
  open -a Docker 2>/dev/null || true
  echo -n "  Waiting for Docker"
  for i in $(seq 1 30); do
    if docker info &>/dev/null; then
      echo ""
      log "Docker is running."
      break
    fi
    echo -n "."
    sleep 2
  done
  if ! docker info &>/dev/null; then
    err "Docker failed to start after 60s. Please start Docker Desktop manually."
    exit 1
  fi
fi

log "Docker is running ($(docker info --format '{{.ServerVersion}}' 2>/dev/null))"

# Check available memory
DOCKER_MEM=$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo "0")
DOCKER_MEM_GB=$(echo "scale=1; $DOCKER_MEM / 1073741824" | bc 2>/dev/null || echo "?")
log "Docker memory: ${DOCKER_MEM_GB}GB allocated"

if [ "${DOCKER_MEM:-0}" -lt 12000000000 ] 2>/dev/null; then
  warn "Recommend at least 16GB memory for Docker (current: ${DOCKER_MEM_GB}GB)"
  warn "Set this in Docker Desktop → Settings → Resources"
fi

# ── Clean mode ───────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--clean" ]]; then
  warn "Clean mode: removing all containers, images, and volumes..."
  docker compose down -v --rmi local 2>/dev/null || true
  log "Clean complete."
fi

# ── Ollama setup ─────────────────────────────────────────────────────────────

step "2/6  Ollama & LLM models"

if ! command -v ollama &>/dev/null; then
  err "Ollama is not installed. Install from https://ollama.com"
  exit 1
fi

if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
  log "Starting Ollama with memory-optimized settings..."
  OLLAMA_MAX_LOADED_MODELS=3 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 \
    ollama serve &>/dev/null &
  OLLAMA_PID=$!
  echo -n "  Waiting for Ollama"
  for i in $(seq 1 20); do
    if curl -sf http://localhost:11434/api/tags &>/dev/null; then
      echo ""
      log "Ollama started (PID $OLLAMA_PID)."
      break
    fi
    echo -n "."
    sleep 2
  done
  if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
    err "Ollama failed to start. Please run manually:"
    err "  OLLAMA_MAX_LOADED_MODELS=3 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 ollama serve"
    exit 1
  fi
else
  log "Ollama is already running."
fi

# Pull required models if missing
MODELS=("qwen2.5-coder:7b" "llama3.1:8b" "nomic-embed-text")
for model in "${MODELS[@]}"; do
  model_base=$(echo "$model" | cut -d: -f1)
  if ! ollama list 2>/dev/null | grep -q "$model_base"; then
    log "Pulling model $model (this may take a few minutes)..."
    ollama pull "$model"
    log "Model $model downloaded."
  else
    log "Model $model ready."
  fi
done

# ── Environment file ─────────────────────────────────────────────────────────

step "3/6  Environment configuration"

if [ ! -f .env ]; then
  log "Creating .env with default settings..."
  cat > .env <<'ENVEOF'
# === Core Infrastructure ===
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=chaosguard
POSTGRES_USER=chaosguard
POSTGRES_PASSWORD=chaosguard_dev_2026

REDIS_HOST=redis
REDIS_PORT=6379

KAFKA_BOOTSTRAP_SERVERS=kafka:9092

CHROMADB_HOST=chromadb
CHROMADB_PORT=8000

OLLAMA_BASE_URL=http://host.docker.internal:11434

# === Ollama Models ===
OLLAMA_CODE_MODEL=qwen2.5-coder:7b
OLLAMA_REASONING_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text

# === Java Gateway ===
GATEWAY_PORT=8080
DATABASE_URL=jdbc:postgresql://postgres:5432/chaosguard
DATABASE_USER=chaosguard
DATABASE_PASSWORD=chaosguard_dev_2026

# === Python Services ===
INDEXER_PORT=8081
AGENTS_PORT=8082
MCP_PORT=5001

# === Frontend ===
FRONTEND_PORT=3000
NEXT_PUBLIC_API_URL=http://localhost:8080

# === Scan Limits ===
MAX_REPO_SIZE_MB=500
MAX_FILE_COUNT=50000
MAX_CONCURRENT_SCANS=3
SCAN_TIMEOUT_MINUTES=60

# === GitHub (optional — needed for Create Issue / Create PR) ===
# GITHUB_TOKEN=ghp_your_token_here

# === Kafka Topics ===
KAFKA_TOPIC_CLONE=repo-clone-events
KAFKA_TOPIC_INDEX=index-events
KAFKA_TOPIC_INDEX_COMPLETE=index-complete
KAFKA_TOPIC_SCAN_PROGRESS=scan-progress
KAFKA_TOPIC_SCAN_COMPLETE=scan-complete
KAFKA_TOPIC_RESULTS_READY=results-ready
ENVEOF
  log ".env created with defaults."
else
  log ".env already exists."
fi

# ── Build and start ─────────────────────────────────────────────────────────

step "4/6  Building and starting services"
echo -e "  ${YELLOW}First run pulls Docker images (~5GB) and builds 5 services. May take 10-15 minutes.${NC}"
echo ""

docker compose up --build -d 2>&1 | grep -E "Built|Started|Created|Running|Pulling|Error" || true

# ── Wait for services ───────────────────────────────────────────────────────

step "5/6  Waiting for services to become healthy"

wait_for_service() {
  local name=$1
  local url=$2
  local max_wait=${3:-120}
  local interval=${4:-3}
  echo -n "  $name"
  for i in $(seq 1 $((max_wait / interval))); do
    if curl -sf "$url" &>/dev/null; then
      echo -e " ${GREEN}✓${NC}"
      return 0
    fi
    echo -n "."
    sleep "$interval"
  done
  echo -e " ${RED}✗ (timeout)${NC}"
  return 1
}

wait_for_service "ChromaDB     " "http://localhost:8000/api/v1/heartbeat" 60
wait_for_service "Gateway      " "http://localhost:8080/actuator/health" 180
wait_for_service "Indexer      " "http://localhost:8081/health" 120
wait_for_service "Agents       " "http://localhost:8082/health" 120
wait_for_service "Frontend     " "http://localhost:3000" 120
wait_for_service "Prometheus   " "http://localhost:9090/-/healthy" 30
wait_for_service "Grafana      " "http://localhost:3002/api/health" 60
wait_for_service "Swagger UI   " "http://localhost:8080/swagger-ui.html" 30

# ── Summary ──────────────────────────────────────────────────────────────────

step "6/6  All systems go!"
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              ChaosGuard AI is running!                      ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Application${NC}                                                 ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Dashboard:     ${CYAN}http://localhost:3000${NC}                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Gateway API:   ${CYAN}http://localhost:8080${NC}                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Swagger UI:    ${CYAN}http://localhost:8080/swagger-ui.html${NC}        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  MCP Server:    ${CYAN}http://localhost:5001${NC}                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Observability${NC}                                               ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Grafana:       ${CYAN}http://localhost:3002${NC}  (admin/admin)         ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Prometheus:    ${CYAN}http://localhost:9090${NC}                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${BOLD}Default login:${NC}  admin / admin                                ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Logs:  ${CYAN}docker compose logs -f [service]${NC}                     ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Stop:  ${CYAN}docker compose down${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Clean: ${CYAN}./start.sh --clean${NC}                                   ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
