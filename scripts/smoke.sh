#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"
max_attempts="${MAX_POLL_ATTEMPTS:-20}"
poll_delay_seconds="${POLL_DELAY_SECONDS:-1}"

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

status=""
status_json=""
for attempt in $(seq 1 "$max_attempts"); do
  status_json="$(curl -fsS "$base_url/v1/job/$job_id")"
  status="$(python - <<'PY' "$status_json"
import json,sys
print(json.loads(sys.argv[1]).get("status", ""))
PY
)"
  echo "poll[$attempt/$max_attempts]: $status_json"

  if [[ "$status" == "succeeded" || "$status" == "failed" ]]; then
    break
  fi

  sleep "$poll_delay_seconds"
done

if [[ "$status" != "succeeded" && "$status" != "failed" ]]; then
  echo "smoke test failed: job did not reach terminal state after $max_attempts polls" >&2
  exit 1
fi

echo "smoke test complete"
