#!/bin/bash
# ChaosGuard - Oracle Cloud Free Tier Setup Script
# Run this on a fresh Oracle Cloud ARM instance (Ampere A1, 4 cores, 24GB RAM)
#
# Prerequisites:
#   1. Create Oracle Cloud Free Tier account: https://cloud.oracle.com/free
#   2. Create an Ampere A1 VM: 4 OCPUs, 24GB RAM, Ubuntu 22.04
#   3. Open ports 8080 (API) in the security list
#   4. SSH into the instance and run this script

set -e

echo "=== Installing Docker ==="
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER

echo "=== Cloning ChaosGuard ==="
git clone https://github.com/Ayush1906saxena/ChaosGuard.git ~/ChaosGuard
cd ~/ChaosGuard

echo "=== Setting up environment ==="
cp deploy/.env.prod.example deploy/.env.prod
echo ""
echo ">>> IMPORTANT: Edit deploy/.env.prod with your values <<<"
echo ">>>   - Set a strong POSTGRES_PASSWORD"
echo ">>>   - Set a random JWT_SECRET (use: openssl rand -hex 32)"
echo ">>>   - Set FRONTEND_URL to your Vercel URL"
echo ""

echo "=== Building and starting services ==="
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d --build

echo "=== Pulling Ollama models (this takes a few minutes) ==="
sleep 30  # Wait for Ollama container to start
docker exec $(docker ps -q -f name=ollama) ollama pull qwen2.5-coder:7b
docker exec $(docker ps -q -f name=ollama) ollama pull nomic-embed-text

echo ""
echo "=== Setup complete! ==="
echo "Gateway API: http://$(curl -s ifconfig.me):8080"
echo ""
echo "Next steps:"
echo "  1. Edit deploy/.env.prod with your values"
echo "  2. Restart: docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.prod up -d"
echo "  3. Deploy frontend to Vercel with NEXT_PUBLIC_API_URL=http://<your-oracle-ip>:8080"
