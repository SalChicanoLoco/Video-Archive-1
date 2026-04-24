# Video-Archive-1

API-agnostic starter scaffold for a video archive transcription service.

## What this includes

- FastAPI service with **versioned API routes** under `/v1`
- Request ID middleware (auto-generates or forwards `X-Request-ID`)
- Structured request logging (method, path, status, duration, request ID)
- Provider abstraction via `TranscriptionProvider`
- Default `mock` provider (no external API dependency)
- **Plugin registration path for provider adapters** via `PROVIDER_PLUGINS`
- **Async transcription job scaffold** (`enqueue` + `poll status`)
- **Switchable job store backend** (`memory` or `sqlite`)
- Container-first workflow with `Dockerfile` + `docker-compose.yml`
- Minimal web UI (`web/`) for browser-based testing
- Optional dev container config in `.devcontainer/devcontainer.json`

## Quick start (no local Python needed)

```bash
cp .env.example .env
docker compose up --build
```

Open:

- API docs/health checks: `http://localhost:8000/v1/health`
- Web UI: `http://localhost:8080`

## Web UI behavior

The web page can:

- run `/v1/health`
- submit `/v1/jobs/transcribe`
- poll `/v1/jobs/{job_id}`

This gives you end-to-end confidence from browser without installing Python on your host.

## API routes

- `GET /`
- `GET /v1/health`
- `GET /v1/providers`
- `POST /v1/transcribe`
- `POST /v1/jobs/transcribe`
- `GET /v1/jobs/{job_id}`

## Provider plugins (drop-in adapters)

Use `PROVIDER_PLUGINS` as a comma-separated list:

```env
PROVIDER_PLUGINS=whisper=app.providers_ext.whisper:WhisperProvider
```

Format:

- `name=module.path:ClassName`

## Job store backend

Use env config to select storage:

- `JOB_STORE_BACKEND=memory` (default)
- `JOB_STORE_BACKEND=sqlite`
- `SQLITE_DB_PATH=data/jobs.db`

## Environment

Copy `.env.example` to `.env` and adjust:

- `APP_NAME`
- `APP_ENV`
- `TRANSCRIPTION_PROVIDER`
- `LOG_LEVEL`
- `PROVIDER_PLUGINS`
- `JOB_STORE_BACKEND`
- `SQLITE_DB_PATH`

## Test

```bash
pytest
```
