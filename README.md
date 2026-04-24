# Video-Archive-1

KISS-first FastAPI service for transcription jobs.

## Product goal (current)

Ship a usable core loop quickly:

1. Enqueue a transcription job.
2. Poll job status.
3. Read transcript (or error) when done.

This repository intentionally keeps advanced features optional so the MVP stays easy to run and reason about.

## MVP endpoints

- `POST /v1/transcribe` — enqueue by source
- `POST /v1/intake` — upload file and enqueue
- `GET /v1/job/{job_id}` — poll status
- `GET /v1/health` — health check

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Open: `http://localhost:8000`

## Environment

- `TRANSCRIPTION_PROVIDER=mock`
- `JOB_STORE_BACKEND=memory|sqlite`
- `SQLITE_DB_PATH=data/jobs.db`
- `API_KEY=`
- `MAX_RETRIES=2`
- `RETRY_BACKOFF_SECONDS=2`

## Error contract

All non-2xx API responses return JSON:

```json
{
  "code": "UNAUTHORIZED|NOT_FOUND|VALIDATION_ERROR|...",
  "message": "human-readable",
  "details": {},
  "request_id": "trace-id"
}
```

## Optional / advanced features

These remain available but are not required for the MVP flow:

- `GET /v1/jobs` and `POST /v1/jobs/prune`
- `GET /v1/job/{job_id}/events`
- `GET /v1/providers`
- provider plugins via `PROVIDER_PLUGINS`
- Prometheus-style metrics endpoint at `/metrics`
- optional Airtable logging hook (`airtable_client.log`)
