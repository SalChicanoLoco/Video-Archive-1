# Video-Archive-1

API-agnostic starter scaffold for a video archive transcription service.

## What this includes

- FastAPI service with **versioned API routes** under `/v1`
- Request ID middleware (auto-generates or forwards `X-Request-ID`)
- Structured request logging (method, path, status, duration, request ID)
- Provider abstraction via `TranscriptionProvider`
- Default `mock` provider (no external API dependency)
- **Plugin registration path for provider adapters** via `PROVIDER_PLUGINS`
- Dockerfile for local container runs
- Basic API tests with `pytest`

## API routes

- `GET /` (service metadata)
- `GET /v1/health`
- `GET /v1/providers`
- `POST /v1/transcribe`

## Provider plugins (drop-in adapters)

Use `PROVIDER_PLUGINS` as a comma-separated list:

```env
PROVIDER_PLUGINS=whisper=app.providers_ext.whisper:WhisperProvider
```

Format:

- `name=module.path:ClassName`

At startup, each plugin class is imported and registered in the provider factory. Plugin classes must inherit `TranscriptionProvider` and be instantiable with no constructor args.

## Run locally

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

## Test

```bash
pytest
```

## Docker

```bash
docker build -t video-archive-api .
docker run --rm -p 8000:8000 --env-file .env video-archive-api
```
