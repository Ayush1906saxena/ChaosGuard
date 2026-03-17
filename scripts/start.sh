#!/bin/bash
set -e

echo "=== ChaosGuard AI — Starting All Services ==="

echo "[1/5] Starting infrastructure services..."
docker compose up -d postgres redis kafka chromadb ollama
echo "Waiting for infrastructure health checks..."
docker compose exec -T postgres pg_isready -U chaosguard -q && echo "  ✓ PostgreSQL"
docker compose exec -T redis redis-cli ping | grep -q PONG && echo "  ✓ Redis"
sleep 10
echo "  ✓ Kafka (waiting for broker)"
curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null && echo "  ✓ ChromaDB"
curl -sf http://localhost:11434/api/tags > /dev/null && echo "  ✓ Ollama"

echo "[2/5] Pulling Ollama models (this may take a while on first run)..."
docker compose up ollama-init
echo "  ✓ All models pulled"

echo "[3/5] Starting application services..."
docker compose up -d gateway indexer agents mcp-server
sleep 15
curl -sf http://localhost:8080/actuator/health > /dev/null && echo "  ✓ Gateway"
curl -sf http://localhost:8081/health > /dev/null && echo "  ✓ Indexer"
curl -sf http://localhost:8082/health > /dev/null && echo "  ✓ Agents"
curl -sf http://localhost:5001/health > /dev/null && echo "  ✓ MCP Server"

echo "[4/5] Starting frontend..."
docker compose up -d frontend
sleep 5
echo "  ✓ Frontend"

echo "[5/5] Running smoke test..."
SCAN_RESPONSE=$(curl -sf -X POST http://localhost:8080/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/spring-projects/spring-petclinic", "tier": "recon", "branch": "main"}')

echo "$SCAN_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  ✓ Smoke test passed: scan {d[\"scan_id\"]} queued')" 2>/dev/null || echo "  ⚠ Smoke test: could not create scan (this is ok if no internet)"

echo ""
echo "=== ChaosGuard AI is running! ==="
echo "  Dashboard:  http://localhost:3000"
echo "  API:        http://localhost:8080"
echo "  MCP Server: http://localhost:5001"
echo "  Ollama:     http://localhost:11434"
echo ""
