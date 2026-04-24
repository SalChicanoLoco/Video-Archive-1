# Video-Archive-1

Container-first FastAPI transcription scaffold with built-in web dashboard.

## Stack decisions

- Flask -> **FastAPI**
- gunicorn -> **uvicorn**
- `@app.route` -> FastAPI decorators (`@app.get`, `@app.post`)

## What this includes

- FastAPI backend on port **8000** (`uvicorn`)
- Static frontend served from same origin (`/` + `/static`)
- Tape status dashboard table + upload intake + progress indicator
- Provider plugin registration (`PROVIDER_PLUGINS`)
- Background task processing for long-running jobs
- Retry/backoff support for transient job failures
- Job polling (`/v1/job/{id}`)
- Job event timeline (`/v1/job/{id}/events`)
- Optional Airtable status logging hook (`airtable_client.log`)
- Optional API key auth (`x-api-key`)
- Streamlined jobs API with filtering and pruning
- GitHub Actions CI for tests + docker smoke checks
- Prometheus-style metrics endpoint (`/metrics`)
- Standardized JSON error contract
- Handoff doc for Claude + Airtable pipeline (`docs/CLAUDE_HANDOFF.md`)

## Run (Docker only)

```bash
cp .env.example .env
docker compose up --build
```

Open browser:

- `http://localhost:8000` (web UI)

## Primary API endpoints

- `POST /v1/transcribe` -> enqueue job, returns `job_id`
- `POST /v1/process` -> enqueue job, returns `job_id`
- `POST /v1/intake` -> multipart file upload + enqueue
- `GET /v1/job/{job_id}` -> job status
- `GET /v1/job/{job_id}/events` -> job event timeline
- `GET /v1/jobs?limit=100&status=queued` -> job listing/filtering
- `POST /v1/jobs/prune?keep_latest=500` -> prune older jobs
- `GET /v1/health`
- `GET /metrics`

## Error contract

All non-2xx API responses return:

```json
{
  "code": "UNAUTHORIZED|NOT_FOUND|VALIDATION_ERROR|...",
  "message": "human-readable",
  "details": {},
  "request_id": "trace-id"
}
```

## Auth

If `API_KEY` is set, protected endpoints require header:

```http
x-api-key: <API_KEY>
```

Protected endpoints: `/v1/transcribe`, `/v1/process`, `/v1/intake`, `/v1/job/{id}`, `/v1/job/{id}/events`, `/v1/jobs`, `/v1/jobs/prune`.

## Retries

- `MAX_RETRIES` controls maximum retry attempts per job.
- `RETRY_BACKOFF_SECONDS` controls exponential backoff base.
- Job status will transition through `retrying` before `failed` when retries remain.

## CI (agent-like safety net)

GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. `pytest -q` on Python 3.12
2. Docker build + runtime smoke test (`scripts/smoke.sh`)

This gives autonomous verification on each push/PR so you are not flying blind.

## Environment

- `TRANSCRIPTION_PROVIDER=mock`
- `PROVIDER_PLUGINS=`
- `JOB_STORE_BACKEND=memory|sqlite`
- `SQLITE_DB_PATH=data/jobs.db`
- `APP_PORT=8000`
- `API_KEY=`
- `MAX_RETRIES=2`
- `RETRY_BACKOFF_SECONDS=2`

## Notes

- If `airtable_client.py` is present, job status events are logged via `airtable_client.log(...)`.
- If missing, jobs still run normally.
