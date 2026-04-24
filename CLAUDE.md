# Video Archive Pipeline — Claude Context

You are helping operate a portable video transcription and EDL generation pipeline
built to process a client's video archive on-site. The pipeline runs in Docker on
any Ubuntu machine (including a USB-boot VM) and produces SRT transcripts and
CMX 3600 EDL files ready for Adobe Premiere Pro.

## What This Project Does

1. Accepts MP4 video files dropped into `video_pipeline/input/`
2. Extracts audio (WAV)
3. Transcribes with OpenAI Whisper (large-v3, running locally in Docker)
4. Generates CMX 3600 EDL selects via Claude (Anthropic API) if a key is available
5. Outputs SRTs and EDLs to `video_pipeline/output/`

The client pays per batch of files processed — getting files through the pipeline
quickly is the primary goal.

## Repository Layout

```
Video-Archive-1/
├── mcp_server.py          ← MCP server (you are using this right now)
├── CLAUDE.md              ← this file
├── setup.sh               ← one-shot Ubuntu bootstrap (installs Docker + registers MCP)
├── requirements-mcp.txt   ← MCP server Python deps
├── video_pipeline/        ← THE WORKING PIPELINE (Flask + Docker)
│   ├── app/
│   │   ├── app.py         ← Flask app, all API endpoints
│   │   ├── config_store.py← Airtable runtime key store
│   │   └── pipeline/      ← audio, transcribe, edl, rename, metadata, utils
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── .env               ← machine-local credentials (never committed)
│   ├── .env.example       ← template (committed)
│   ├── process_batch.sh   ← batch processor script
│   ├── input/             ← drop MP4s here
│   └── output/            ← SRTs and EDLs appear here
├── app/                   ← incomplete FastAPI rewrite (DO NOT USE for processing)
└── web/                   ← future web UI (not active)
```

**Important:** The `app/` directory at the repo root is an incomplete FastAPI rewrite.
All actual processing goes through `video_pipeline/`. Always use the Flask pipeline.

## Architecture: Key Management

The pipeline uses a two-tier credential strategy so no sensitive keys need to
travel on the USB stick:

| Credential | Where it lives |
|---|---|
| `AIRTABLE_API_KEY` | `video_pipeline/.env` (on the stick) |
| `AIRTABLE_BASE_ID` | `video_pipeline/.env` (on the stick) |
| `ANTHROPIC_API_KEY` | Airtable "Config" table (fetched at runtime) |

At startup, `config_store.py` pulls all keys from the Airtable Config table.
If Airtable is unreachable, the pipeline degrades gracefully to SRT-only mode
(no EDL generation, but transcription still works).

**Airtable Config table structure** (create once in Mark's base):
- Table name: `Config`
- Column: `Key` (Single line text)
- Column: `Value` (Single line text)
- Row: Key = `ANTHROPIC_API_KEY`, Value = `sk-ant-...`

## MCP Tools Available

You have these tools to operate the pipeline. Use them in order for a fresh setup:

| Tool | When to use |
|---|---|
| `check_environment()` | First thing — verify Docker, dirs, .env are ready |
| `connect_airtable(api_key, base_id)` | Save creds and test Airtable connection |
| `start_pipeline()` | Start Docker containers (builds image on first run) |
| `pipeline_status()` | Full status: containers, API health, key availability, file counts |
| `process_batch(input_dir)` | Kick off transcription + EDL for all MP4s |
| `get_logs(lines)` | Watch container logs for progress/errors |
| `reload_config()` | Refresh Airtable config without restarting containers |
| `stop_pipeline()` | Shut down when done |
| `set_env_var(key, value)` | Tweak non-credential settings (WHISPER_MODEL_SIZE etc.) |

## Standard Setup Flow

When arriving at a new machine with this repo cloned:

```
1. check_environment()
   → Fix any FAILs before continuing

2. connect_airtable(api_key="pat...", base_id="app...")
   → Saves to .env, tests connection, reports whether ANTHROPIC_API_KEY is in Airtable

3. start_pipeline()
   → First run: pulls Docker image + downloads Whisper large-v3 (~10 min, ~3 GB)
   → Subsequent runs: ~30 seconds

4. pipeline_status()
   → Confirm everything is green before processing

5. process_batch()
   → Runs in background; check get_logs() for progress
   → Results in video_pipeline/output/

6. (optional) reload_config()
   → If Mark adds ANTHROPIC_API_KEY to Airtable mid-session, reload without restart
```

## Typical Conversation Starters

- "Hey Claude, I'm ready to set up the Video-Archive-1 environment"
  → Run check_environment(), then walk through connect_airtable() → start_pipeline()

- "Set up the pipeline from scratch"
  → Full setup flow above

- "We're ready to process files"
  → check pipeline_status(), then process_batch()

- "The Anthropic key is in Airtable now"
  → reload_config() and confirm EDL is enabled

- "Something's wrong with the pipeline"
  → pipeline_status() then get_logs() to diagnose

## API Endpoints (when pipeline is running at http://localhost:5000)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Liveness + Whisper model status |
| `/setup` | GET | Browser wizard (Airtable connect UI) |
| `/setup/connect` | POST | Save + test Airtable creds |
| `/setup/reload` | POST | Reload config from Airtable |
| `/extract-audio` | POST | `{"path": "/app/input/file.mp4"}` |
| `/transcribe` | POST | `{"audio_path": "/app/output/file.wav"}` → `{"job_id": "..."}` |
| `/jobs/<id>` | GET | Poll transcription job status |
| `/generate-edl` | POST | `{"srt_path": "...", "tape_id": "...", "theme": "selects"}` |
| `/process` | POST | Full pipeline on one file (synchronous) |

## Whisper Model Sizes

Default is `large-v3`. Override in `.env` before building:
```
WHISPER_MODEL_SIZE=medium   # faster, less accurate
WHISPER_MODEL_SIZE=large-v3 # best accuracy (default)
```
Or via: `set_env_var("WHISPER_MODEL_SIZE", "medium")` then restart.

## Troubleshooting

**Pipeline won't start:**
- `get_logs()` — look for OOM or port conflicts
- Check Docker has enough memory (Whisper large-v3 needs ~4 GB RAM)
- `docker compose down && docker compose up -d` if containers are stuck

**Transcription stuck / slow:**
- Normal: large-v3 does ~10-20 min real-time on CPU for a 1-hour video
- `get_logs()` to see progress

**EDL not being generated:**
- `reload_config()` — check "Anthropic key: ✓" in output
- If ✗, ensure ANTHROPIC_API_KEY is in the Airtable Config table

**Can't connect to Airtable:**
- Check token hasn't expired (Airtable PATs have expiry dates)
- Pipeline falls back to SRT-only — transcription still works

**Port 5000 conflict:**
- `docker compose down` then `docker compose up -d`
- Or change port in `video_pipeline/docker-compose.yml` ports section

## Notes

- Input/output use **bind mounts** — files you drop in `video_pipeline/input/` are
  immediately visible to the container. No copying needed.
- The Whisper model is baked into the Docker image during `docker compose build`.
  After the first build it's cached — rebuilds are fast.
- `process_batch.sh` polls job status every 30s and has a 6-hour timeout per file.
- All output files (WAV, SRT, EDL) land in `video_pipeline/output/` alongside each other.
