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
- Dockerfile for local container runs
- Dev container configuration in `.devcontainer/devcontainer.json`
- Basic API tests with `pytest`

## API routes

- `GET /` (service metadata)
- `GET /v1/health`
- `GET /v1/providers`
- `POST /v1/transcribe`
- `POST /v1/jobs/transcribe` (returns `202` + `job_id`)
- `GET /v1/jobs/{job_id}`

## Provider plugins (drop-in adapters)

Use `PROVIDER_PLUGINS` as a comma-separated list:

```env
PROVIDER_PLUGINS=whisper=app.providers_ext.whisper:WhisperProvider
```

Format:

- `name=module.path:ClassName`

At startup, each plugin class is imported and registered in the provider factory. Plugin classes must inherit `TranscriptionProvider` and be instantiable with no constructor args.

## Async job flow

1. Call `POST /v1/jobs/transcribe` with `{ "source": "video.mp4" }`.
2. Receive `{ "job_id": "...", "status": "queued" }`.
3. Poll `GET /v1/jobs/{job_id}` until status is `succeeded` or `failed`.

## Job store backend

Use env config to select storage:

- `JOB_STORE_BACKEND=memory` (default; in-memory for local/dev)
- `JOB_STORE_BACKEND=sqlite` (persists jobs to SQLite file)
- `SQLITE_DB_PATH=data/jobs.db` (path used when backend is `sqlite`)

## Dev container workflow (no local Python install needed)

If you do not want to run anything on your host machine:

1. Open this folder in VS Code.
2. Install "Dev Containers" extension.
3. Run **Dev Containers: Reopen in Container**.
4. The container will auto-run:
   - `pip install --no-cache-dir -r requirements.txt`
5. Then run inside the container terminal:

```bash
uvicorn app.main:app --reload
pytest
```

## Run locally (optional)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/v1/transcribe \
  -H 'content-type: application/json' \
  -H 'x-request-id: my-request-001' \
  -d '{"source":"sample.mp4"}'
```

Optional provider override (per request):

```bash
curl -X POST http://127.0.0.1:8000/v1/transcribe \
  -H 'content-type: application/json' \
  -d '{"source":"sample.mp4","provider":"mock"}'
```

## Environment

Copy `.env.example` to `.env` and adjust:

- `APP_NAME` (default: `Video Archive API`)
- `APP_ENV` (default: `dev`)
- `TRANSCRIPTION_PROVIDER` (default: `mock`)
- `LOG_LEVEL` (default: `INFO`)
- `PROVIDER_PLUGINS` (default: empty)
- `JOB_STORE_BACKEND` (default: `memory`)
- `SQLITE_DB_PATH` (default: `data/jobs.db`)

## Test

```bash
pytest
```

## Docker

```bash
docker build -t video-archive-api .
docker run --rm -p 8000:8000 --env-file .env video-archive-api
```
