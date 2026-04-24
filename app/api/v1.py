from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Request, UploadFile

from app.config import settings
from app.jobs.service import enqueue_job, job_store, run_transcription_job
from app.providers.factory import list_supported_providers
from app.schemas.transcription import (
    ProvidersResponse,
    TranscriptionJobRequest,
    TranscriptionJobResponse,
    TranscriptionJobsListResponse,
    TranscriptionJobStatusResponse,
)

router = APIRouter(prefix="/v1", tags=["v1"])


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Require x-api-key only when API_KEY is configured."""
    if not settings.api_key:
        return

    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "provider": settings.transcription_provider,
        "api_version": "v1",
        "request_id": request.state.request_id,
    }


@router.get("/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    return ProvidersResponse(
        configured_provider=settings.transcription_provider,
        supported_providers=list_supported_providers(),
    )


def _enqueue(payload: TranscriptionJobRequest, background_tasks: BackgroundTasks) -> TranscriptionJobResponse:
    provider_name = payload.provider or settings.transcription_provider
    record = enqueue_job(source=payload.source, provider=provider_name)
    background_tasks.add_task(run_transcription_job, record.job_id)
    return TranscriptionJobResponse(job_id=record.job_id, status=record.status)


@router.post("/transcribe", response_model=TranscriptionJobResponse, status_code=202)
async def transcribe(
    payload: TranscriptionJobRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobResponse:
    return _enqueue(payload, background_tasks)


@router.post("/process", response_model=TranscriptionJobResponse, status_code=202)
async def process(
    payload: TranscriptionJobRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobResponse:
    return _enqueue(payload, background_tasks)


@router.post("/intake", response_model=TranscriptionJobResponse, status_code=202)
async def intake(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobResponse:
    uploads_dir = Path("/srv/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target = uploads_dir / file.filename
    content = await file.read()
    target.write_bytes(content)

    payload = TranscriptionJobRequest(source=str(target), provider=settings.transcription_provider)
    return _enqueue(payload, background_tasks)


@router.get("/job/{job_id}", response_model=TranscriptionJobStatusResponse)
async def get_job(job_id: str, _auth: None = Depends(require_api_key)) -> TranscriptionJobStatusResponse:
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return TranscriptionJobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        source=record.source,
        provider=record.provider,
        result_text=record.result_text,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/jobs", response_model=TranscriptionJobsListResponse)
async def list_jobs(
    limit: int = 100,
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobsListResponse:
    records = job_store.list_jobs(limit=limit)
    return TranscriptionJobsListResponse(
        jobs=[
            TranscriptionJobStatusResponse(
                job_id=r.job_id,
                status=r.status,
                source=r.source,
                provider=r.provider,
                result_text=r.result_text,
                error=r.error,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in records
        ]
    )
