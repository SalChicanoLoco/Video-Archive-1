#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"

health_json="$(curl -fsS "$base_url/v1/health")"
echo "health: $health_json"

job_json="$(curl -fsS -X POST "$base_url/v1/transcribe" \
  -H 'content-type: application/json' \
  -d '{"source":"smoke.mp4"}')"
echo "enqueue: $job_json"

job_id="$(python - <<'PY' "$job_json"
import json,sys
print(json.loads(sys.argv[1])["job_id"])
PY
)"

status_json="$(curl -fsS "$base_url/v1/job/$job_id")"
echo "status: $status_json"

echo "smoke test complete"
