#!/bin/bash
#
# Test script for the video processing pipeline.
#
# This script runs inside the Docker container to verify that each API
# endpoint behaves as expected. It downloads a small sample video, then
# exercises the rename, embed‑metadata, extract‑audio, transcribe and
# process endpoints. At the end, it prints PASS or FAIL for each
# operation and leaves the output files in /app/output for manual
# inspection.

set -euo pipefail

API_URL="http://localhost:5000"
INPUT_DIR="/app/input"
OUTPUT_DIR="/app/output"

# Colours for output
GREEN="\e[32m"
RED="\e[31m"
NC="\e[0m"

# Helper to print pass/fail messages
pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; }

# Wait for the API to be healthy
echo "Waiting for API to become healthy..."
for i in {1..30}; do
  if curl -s "$API_URL/health" | grep -q '"status":\s*"ok"'; then
    echo "API is ready"
    break
  fi
  sleep 2
done

# Create input/output directories if they don't exist
mkdir -p "$INPUT_DIR" "$OUTPUT_DIR"

# Download sample video
SAMPLE_URL="https://archive.org/download/SampleVideo1280x7205mb/SampleVideo_1280x720_5mb.mp4"
SAMPLE_FILE="$INPUT_DIR/sample.mp4"
if [ ! -f "$SAMPLE_FILE" ]; then
  echo "Downloading sample video..."
  curl -L "$SAMPLE_URL" -o "$SAMPLE_FILE"
fi

# 1. Rename
NEW_NAME="TAPE_001_$(date +%Y%m%d)_Test.mp4"
resp=$(curl -s -X POST "$API_URL/rename" -H "Content-Type: application/json" -d "{\"path\": \"$SAMPLE_FILE\", \"new_name\": \"$NEW_NAME\"}")
new_path=$(python - <<'PY'
import sys, json, os
data=json.load(sys.stdin)
print(data.get('new_path',''))
PY
 <<< "$resp")
if [ -n "$new_path" ] && [ -f "$new_path" ]; then
  pass "rename endpoint"
else
  echo "$resp"
  fail "rename endpoint"
fi

# 2. Embed metadata
resp2=$(curl -s -X POST "$API_URL/embed-metadata" -H "Content-Type: application/json" -d "{\"path\": \"$new_path\", \"title\": \"Test Video\", \"date\": \"2020-01-01\", \"comment\": \"Test comment\"}")
if echo "$resp2" | grep -q '"path"'; then
  pass "embed-metadata endpoint"
else
  echo "$resp2"
  fail "embed-metadata endpoint"
fi

# 3. Extract audio
resp3=$(curl -s -X POST "$API_URL/extract-audio" -H "Content-Type: application/json" -d "{\"path\": \"$new_path\", \"format\": \"wav\"}")
audio_path=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('audio_path',''))
PY
 <<< "$resp3")
if [ -n "$audio_path" ] && [ -f "$audio_path" ]; then
  pass "extract-audio endpoint"
else
  echo "$resp3"
  fail "extract-audio endpoint"
fi

# 4. Transcribe (asynchronous)
resp4=$(curl -s -X POST "$API_URL/transcribe" -H "Content-Type: application/json" -d "{\"audio_path\": \"$audio_path\"}")
job_id=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('job_id',''))
PY
 <<< "$resp4")
if [ -z "$job_id" ]; then
  echo "$resp4"
  fail "transcribe endpoint (job submission)"
else
  pass "transcribe endpoint (job submission)"
fi

# Poll job status until finished or timeout
echo "Waiting for transcription job $job_id to finish..."
for i in {1..60}; do
  status_resp=$(curl -s "$API_URL/jobs/$job_id")
  status=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('status',''))
PY
 <<< "$status_resp")
  if [ "$status" = "finished" ]; then
    srt_path=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('result',{}).get('srt_path',''))
PY
 <<< "$status_resp")
    if [ -n "$srt_path" ] && [ -f "$srt_path" ]; then
      pass "transcription job"
    else
      fail "transcription job (file missing)"
    fi
    break
  elif [ "$status" = "failed" ]; then
    echo "$status_resp"
    fail "transcription job failed"
    break
  fi
  sleep 5
done

# 5. Full process
resp5=$(curl -s -X POST "$API_URL/process" -H "Content-Type: application/json" -d "{\"path\": \"$new_path\", \"title\": \"Full Test\", \"date\": \"2021-12-31\", \"comment\": \"Full pipeline test\"}")
renamed_path=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('renamed_path',''))
PY
 <<< "$resp5")
audio_path2=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('audio_path',''))
PY
 <<< "$resp5")
srt_path2=$(python - <<'PY'
import sys, json
data=json.load(sys.stdin)
print(data.get('srt_path',''))
PY
 <<< "$resp5")
if [ -n "$renamed_path" ] && [ -f "$renamed_path" ] && [ -n "$audio_path2" ] && [ -f "$audio_path2" ] && [ -n "$srt_path2" ] && [ -f "$srt_path2" ]; then
  pass "process endpoint"
else
  echo "$resp5"
  fail "process endpoint"
fi

echo "Test pipeline completed. Outputs are in $OUTPUT_DIR"