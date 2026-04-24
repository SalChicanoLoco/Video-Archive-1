from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from app.config import settings
from app.jobs.service import job_store, run_transcription_job
from app.providers.factory import (
    UnsupportedProviderError,
    get_provider,
    list_supported_providers,
)
from app.schemas.transcription import (
    ProvidersResponse,
    TranscriptionJobRequest,
    TranscriptionJobResponse,
    TranscriptionJobStatusResponse,
    TranscriptionRequest,
    TranscriptionResponse,
)

router = APIRouter(prefix="/v1", tags=["v1"])


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


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(payload: TranscriptionRequest) -> TranscriptionResponse:
    provider_name = payload.provider or settings.transcription_provider

    try:
        provider = get_provider(provider_name)
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await provider.transcribe(payload.source)
    return TranscriptionResponse(text=result.text, provider=result.provider)


@router.post("/jobs/transcribe", response_model=TranscriptionJobResponse, status_code=202)
async def enqueue_transcription(
    payload: TranscriptionJobRequest,
    background_tasks: BackgroundTasks,
) -> TranscriptionJobResponse:
    provider_name = payload.provider or settings.transcription_provider
    record = job_store.create_job(source=payload.source, provider=provider_name)
    background_tasks.add_task(run_transcription_job, record.job_id)
    return TranscriptionJobResponse(job_id=record.job_id, status=record.status)


@router.get("/jobs/{job_id}", response_model=TranscriptionJobStatusResponse)
async def get_job(job_id: str) -> TranscriptionJobStatusResponse:
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
