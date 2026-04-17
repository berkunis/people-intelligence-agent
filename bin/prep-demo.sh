#!/usr/bin/env bash
# Pre-interview demo prep. Run this 2 minutes before the call.
# It is idempotent — safe to run multiple times.
#
#   1. Ensure Colima is running
#   2. Bring up Grafana + Prometheus + Pushgateway
#   3. Wait for them to be healthy
#   4. Fire one sanity-check query against the agent
#   5. Open Grafana in the browser
#
# Exit 0 = ready to go. Anything else = fix before the interview.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
red() { printf "\033[31m%s\033[0m\n" "$*"; }
dim() { printf "\033[2m%s\033[0m\n" "$*"; }

step() { printf "\n\033[1;36m▸ %s\033[0m\n" "$*"; }

step "1/6  Check Colima"
if ! colima status >/dev/null 2>&1; then
  yellow "Colima not running — starting it (takes ~30s)..."
  colima start
else
  green "✓ Colima is running"
fi

step "2/6  Check warehouse exists"
if [[ ! -f data/warehouse/pia.duckdb ]]; then
  yellow "Warehouse missing — seeding synthetic data..."
  uv run python -m data.synthetic.generate
  uv run python -m storage.load_raw
else
  green "✓ Warehouse ready ($(du -h data/warehouse/pia.duckdb | cut -f1))"
fi

step "3/6  Bring up docker stack"
docker compose -f infra/docker-compose.yml up -d 2>&1 | grep -E "Started|Running|Created" || true
green "✓ docker compose up"

step "4/6  Wait for services to be healthy (timeout 30s)"
for i in {1..30}; do
  push_ok=$(curl -fs -o /dev/null -w "%{http_code}" http://localhost:9091/metrics 2>/dev/null || echo "000")
  prom_ok=$(curl -fs -o /dev/null -w "%{http_code}" http://localhost:9090/-/ready 2>/dev/null || echo "000")
  graf_ok=$(curl -fs -o /dev/null -w "%{http_code}" http://localhost:3000/api/health 2>/dev/null || echo "000")
  if [[ "$push_ok" == "200" && "$prom_ok" == "200" && "$graf_ok" == "200" ]]; then
    green "✓ pushgateway + prometheus + grafana all healthy"
    break
  fi
  printf "."
  sleep 1
  if [[ $i == 30 ]]; then
    red "✗ Services didn't become healthy in 30s."
    red "   pushgateway=$push_ok prometheus=$prom_ok grafana=$graf_ok"
    red "   Run: docker compose -f infra/docker-compose.yml logs"
    exit 1
  fi
done

step "5/6  Smoke test — ask the agent one question"
if [[ ! -f .env ]] || ! grep -q "^ANTHROPIC_API_KEY=sk-" .env 2>/dev/null; then
  red "✗ .env is missing or has no ANTHROPIC_API_KEY."
  red "   Paste your key into .env before the interview."
  exit 2
fi

set +e
output=$(uv run pia ask "What is active headcount by org?" 2>&1)
rc=$?
set -e
if [[ $rc -ne 0 ]]; then
  red "✗ Agent smoke test failed. Output:"
  echo "$output" | tail -20
  exit 3
fi
latency=$(echo "$output" | grep -oE "latency\s+[0-9]+\s*ms" | head -1 || echo "?")
cost=$(echo "$output" | grep -oE '\$0\.[0-9]+' | head -1 || echo "?")
green "✓ Agent answered — $latency · $cost"

step "6/6  Open Grafana dashboard"
open "http://localhost:3000/d/pia-agent-overview" 2>/dev/null || true
green "✓ Dashboard opened"

echo ""
green "═══════════════════════════════════════════════════════════"
green "  Ready for the interview."
green "  Grafana:    http://localhost:3000/d/pia-agent-overview"
green "  Prometheus: http://localhost:9090"
green "  Pushgateway: http://localhost:9091/metrics"
green "═══════════════════════════════════════════════════════════"
