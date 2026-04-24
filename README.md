# Video-Archive-1

Container-first FastAPI transcription scaffold with built-in web dashboard.

## Stack decisions

- Flask -> **FastAPI**
- gunicorn -> **uvicorn**
- `@app.route` -> FastAPI decorators (`@app.get`, `@app.post`)

## What this includes

- FastAPI backend on port **8000** (`uvicorn`)
- Static frontend served from same origin (`/` + `/static`)
- Tape status dashboard table
- File upload/intake form
- Job progress indicator
- Provider plugin registration (`PROVIDER_PLUGINS`)
- Background task processing for long-running jobs
- Job polling (`/v1/job/{id}`)
- Optional Airtable status logging hook (`airtable_client.log`)

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
- `GET /v1/jobs` -> dashboard listing
- `GET /v1/health`

## Background tasks

Long-running operations use FastAPI `BackgroundTasks` so requests return quickly and UI stays responsive.

## Environment

- `TRANSCRIPTION_PROVIDER=mock`
- `PROVIDER_PLUGINS=`
- `JOB_STORE_BACKEND=memory|sqlite`
- `SQLITE_DB_PATH=data/jobs.db`
- `APP_PORT=8000`

## Notes

- If `airtable_client.py` is present, job status events are logged via `airtable_client.log(...)`.
- If missing, jobs still run normally.
