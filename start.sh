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
NC='\033[0m'

banner() {
  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║         ⚔️  ChaosGuard AI  ⚔️               ║${NC}"
  echo -e "${CYAN}║    AI-Powered Security Analysis Platform    ║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
  echo ""
}

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; }

# ── Pre-flight checks ───────────────────────────────────────────────────────

banner

echo -e "${CYAN}Running pre-flight checks...${NC}"

# Check Docker
if ! command -v docker &>/dev/null; then
  err "Docker is not installed. Please install Docker Desktop first."
  exit 1
fi

if ! docker info &>/dev/null; then
  warn "Docker daemon is not running. Attempting to start Docker Desktop..."
  open -a Docker 2>/dev/null || true
  echo -n "Waiting for Docker"
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

# ── Ensure Ollama is running with optimized settings ─────────────────────

if ! command -v ollama &>/dev/null; then
  err "Ollama is not installed. Install from https://ollama.com"
  exit 1
fi

if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
  log "Starting Ollama with memory-optimized settings..."
  OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 \
    ollama serve &>/dev/null &
  sleep 3
  if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
    warn "Ollama may still be starting, continuing..."
  else
    log "Ollama started."
  fi
else
  log "Ollama is already running."
  warn "For best performance, restart Ollama with:"
  warn "  OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_NUM_PARALLEL=1 OLLAMA_FLASH_ATTENTION=1 ollama serve"
fi

# Pull required models if missing
for model in qwen2.5-coder:7b llama3.1:8b nomic-embed-text; do
  if ! ollama list | grep -q "$(echo $model | cut -d: -f1)"; then
    log "Pulling model $model..."
    ollama pull "$model"
  else
    log "Model $model already available."
  fi
done

# ── Check .env ───────────────────────────────────────────────────────────────

if [ ! -f .env ]; then
  err ".env file not found. Creating from defaults..."
  cat > .env <<'ENVEOF'
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
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CODE_MODEL=qwen2.5-coder:7b
OLLAMA_REASONING_MODEL=llama3.1:8b
OLLAMA_EMBED_MODEL=nomic-embed-text
MAX_CONCURRENT_SCANS=3
ENVEOF
  log ".env created."
fi

# ── Build and start ─────────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}Building and starting all services...${NC}"
echo -e "${YELLOW}First run will pull images & LLM models (~15GB). This may take 10-20 minutes.${NC}"
echo ""

docker compose up --build -d 2>&1 | grep -v "^$"

# ── Wait for services ───────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}Waiting for services to become healthy...${NC}"

wait_for_service() {
  local name=$1
  local url=$2
  local max_wait=${3:-120}
  echo -n "  Waiting for $name"
  for i in $(seq 1 $max_wait); do
    if curl -sf "$url" &>/dev/null; then
      echo -e " ${GREEN}✓${NC}"
      return 0
    fi
    echo -n "."
    sleep 2
  done
  echo -e " ${RED}✗ (timeout after ${max_wait}s)${NC}"
  return 1
}

wait_for_service "PostgreSQL" "http://localhost:5432" 30 2>/dev/null || true
wait_for_service "Redis" "http://localhost:6379" 30 2>/dev/null || true
wait_for_service "Kafka" "http://localhost:9092" 60 2>/dev/null || true
wait_for_service "ChromaDB" "http://localhost:8000/api/v1/heartbeat" 60
wait_for_service "Ollama" "http://localhost:11434/api/tags" 60
wait_for_service "Gateway" "http://localhost:8080/actuator/health" 180
wait_for_service "Indexer" "http://localhost:8081/health" 120
wait_for_service "Agents" "http://localhost:8082/health" 120
wait_for_service "Frontend" "http://localhost:3000" 120

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                ChaosGuard AI is running!                    ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Frontend:    ${CYAN}http://localhost:3000${NC}                          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Gateway API: ${CYAN}http://localhost:8080${NC}                          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  MCP Server:  ${CYAN}http://localhost:5001${NC}                          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  Quick scan (curl):                                          ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${YELLOW}curl -X POST http://localhost:8080/api/v1/scans \\${NC}           ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${YELLOW}  -H 'Content-Type: application/json' \\${NC}                   ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${YELLOW}  -d '{\"repoUrl\":\"https://github.com/OWASP/NodeGoat\",${NC}   ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  ${YELLOW}       \"tier\":\"RECON\"}'${NC}                                     ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Logs:  ${CYAN}docker compose logs -f [service]${NC}                     ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  Stop:  ${CYAN}docker compose down${NC}                                  ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}                                                              ${GREEN}║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
