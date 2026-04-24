#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed. Run: sudo bash scripts/bootstrap_ubuntu.sh" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

docker compose up --build -d

echo "Waiting for health endpoint..."
for i in {1..30}; do
  if curl -fsS http://127.0.0.1:8000/v1/health >/dev/null; then
    echo "Service is healthy: http://127.0.0.1:8000"
    exit 0
  fi
  sleep 1
done

echo "Service did not become healthy in time." >&2
docker compose logs --tail=100 api || true
exit 1
