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

## USB-drive workflow (portable machine setup)

If your source files are on an external USB drive, mount that drive into
`/srv/app/uploads` so the container can ingest files directly.

### Option A: run from this repo and override uploads mount

```bash
USB_PATH="/path/to/your/usb"
docker run --rm -it \
  --env-file .env \
  -p 8000:8000 \
  -v "$USB_PATH:/srv/app/uploads" \
  -v "$(pwd)/data:/srv/app/data" \
  "$(docker build -q .)"
```

### Option B: copy/symlink files from USB into local `./uploads`

`docker-compose.yml` already mounts `./uploads` to `/srv/app/uploads`, so you can
copy source files there and use `POST /v1/intake`.

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

## Deferred (currently not exposed as API routes)

These capabilities may return in a later phase, but are intentionally not part of
the current MVP surface:

- job listing/pruning routes
- job event timeline route
- provider discovery route

Still available as implementation options:

- provider plugins via `PROVIDER_PLUGINS`
- Prometheus-style metrics endpoint at `/metrics`
- optional Airtable logging hook (`airtable_client.log`)
