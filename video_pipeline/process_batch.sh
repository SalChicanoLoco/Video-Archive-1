#!/usr/bin/env bash
# Process all MP4 files through the pipeline and produce SRT transcripts.
#
# Usage:
#   bash process_batch.sh                        # processes ./input/*.mp4
#   bash process_batch.sh /mnt/ssd/marks_videos  # processes files in another dir
#
# The service must already be running: docker compose up -d
# Results (WAV + SRT) land in ./output/

set -uo pipefail

API="http://localhost:5000"
INPUT_DIR="${1:-./input}"
LOG_FILE="batch_$(date +%Y%m%d_%H%M%S).log"
POLL_INTERVAL=30   # seconds between status checks
JOB_TIMEOUT=21600  # 6 hours max per file

# ── Colors ────────────────────────────────────────────────────────────────────
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; B='\033[0;34m'; NC='\033[0m'
ok()   { local m="✓ PASS: $1"; echo -e "${G}${m}${NC}"; echo "$m" >> "$LOG_FILE"; }
fail() { local m="✗ FAIL: $1"; echo -e "${R}${m}${NC}"; echo "$m" >> "$LOG_FILE"; }
info() { echo -e "${Y}→${NC} $1"; }
hdr()  { echo -e "${B}$1${NC}"; }

# ── Wait for API ──────────────────────────────────────────────────────────────
hdr "Waiting for pipeline API at $API..."
for i in $(seq 1 30); do
    if curl -sf "$API/health" >/dev/null 2>&1; then
        ok "API is ready"
        break
    fi
    [ "$i" -eq 30 ] && { fail "API did not respond after 60s — is the service running?"; exit 1; }
    sleep 2
done

# ── Collect files ─────────────────────────────────────────────────────────────
INPUT_DIR="$(realpath "$INPUT_DIR")"
mapfile -t FILES < <(find "$INPUT_DIR" -maxdepth 1 -iname "*.mp4" | sort)

if [ "${#FILES[@]}" -eq 0 ]; then
    echo "No MP4 files found in $INPUT_DIR"
    exit 0
fi

echo ""
hdr "Found ${#FILES[@]} file(s) in $INPUT_DIR"
echo "Log: $LOG_FILE"
echo ""

TOTAL=0; PASSED=0; FAILED=0

# ── Process each file ─────────────────────────────────────────────────────────
for mp4 in "${FILES[@]}"; do
    TOTAL=$((TOTAL + 1))
    filename="$(basename "$mp4")"
    # Path as seen inside the container
    container_path="/app/input/$filename"

    hdr "[$TOTAL/${#FILES[@]}] $filename"

    # ── Step 1: Extract audio ────────────────────────────────────────────────
    info "  Extracting audio..."
    audio_resp=$(curl -sf -X POST "$API/extract-audio" \
        -H "Content-Type: application/json" \
        -d "{\"path\": \"$container_path\"}" 2>&1) || {
        fail "$filename — audio extract failed (is the file in ./input/ ?)"
        FAILED=$((FAILED + 1)); continue
    }

    audio_path=$(python3 -c "import sys,json; print(json.loads('$audio_resp')['audio_path'])" 2>/dev/null) || {
        fail "$filename — unexpected audio response: $audio_resp"
        FAILED=$((FAILED + 1)); continue
    }
    info "  Audio: $audio_path"

    # ── Step 2: Submit transcription job ─────────────────────────────────────
    info "  Submitting transcription..."
    trans_resp=$(curl -sf -X POST "$API/transcribe" \
        -H "Content-Type: application/json" \
        -d "{\"audio_path\": \"$audio_path\"}" 2>&1) || {
        fail "$filename — transcription submission failed"
        FAILED=$((FAILED + 1)); continue
    }

    job_id=$(python3 -c "import sys,json; print(json.loads('$trans_resp')['job_id'])" 2>/dev/null) || {
        fail "$filename — no job_id in response: $trans_resp"
        FAILED=$((FAILED + 1)); continue
    }
    info "  Job ID: $job_id"

    # ── Step 3: Poll until done ───────────────────────────────────────────────
    elapsed=0
    while true; do
        status_resp=$(curl -sf "$API/jobs/$job_id" 2>/dev/null || echo '{"status":"unknown"}')
        status=$(python3 -c "import sys,json; print(json.loads('$status_resp').get('status','unknown'))" 2>/dev/null)

        case "$status" in
            finished)
                srt=$(python3 -c "import sys,json; d=json.loads('$status_resp'); print(d.get('result',{}).get('srt_path',''))" 2>/dev/null)

                # ── Step 4: Generate EDL (if ANTHROPIC_API_KEY is set) ───────
                edl_result=""
                if [ -n "${ANTHROPIC_API_KEY:-}" ] && [ -n "$srt" ]; then
                    tape_id="$(basename "$mp4" .mp4)"
                    theme="${EDL_THEME:-selects}"
                    criteria="${EDL_CRITERIA:-Select the most significant, clearly spoken moments. Prefer complete thoughts over fragments.}"
                    info "  Generating EDL (Claude)…"
                    edl_resp=$(curl -sf -X POST "$API/generate-edl" \
                        -H "Content-Type: application/json" \
                        -d "{\"srt_path\": \"$srt\", \"tape_id\": \"$tape_id\", \"theme\": \"$theme\", \"criteria\": \"$criteria\"}" 2>&1) || true
                    edl_result=$(python3 -c "import sys,json; d=json.loads('$edl_resp'); print(d.get('edl_path','') or d.get('error',''))" 2>/dev/null || echo "EDL skipped")
                    info "  EDL: $edl_result"
                fi

                ok "$filename → SRT: $srt${edl_result:+ | EDL: $edl_result}"
                PASSED=$((PASSED + 1))
                break
                ;;
            failed)
                err=$(python3 -c "import sys,json; print(json.loads('$status_resp').get('error','unknown error'))" 2>/dev/null)
                fail "$filename — transcription failed: $err"
                FAILED=$((FAILED + 1))
                break
                ;;
            *)
                if [ "$elapsed" -ge "$JOB_TIMEOUT" ]; then
                    fail "$filename — timed out after $((JOB_TIMEOUT/3600))h"
                    FAILED=$((FAILED + 1))
                    break
                fi
                echo -e "    ${Y}…${NC} ${elapsed}s elapsed (status: $status)"
                sleep "$POLL_INTERVAL"
                elapsed=$((elapsed + POLL_INTERVAL))
                ;;
        esac
    done
    echo ""
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
printf "  Total: %d  |  " "$TOTAL"
echo -e "${G}Passed: $PASSED${NC}  |  ${R}Failed: $FAILED${NC}"
echo "  Full log: $LOG_FILE"
echo "  Results:  ./output/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

[ "$FAILED" -gt 0 ] && exit 1 || exit 0
