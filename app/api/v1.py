from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Request, UploadFile

from app.config import settings
from app.jobs.service import (
    enqueue_job,
    job_store,
    run_transcription_job,
    to_job_status_response,
)
from app.schemas.errors import ErrorResponse
from app.schemas.transcription import (
    TranscriptionJobRequest,
    TranscriptionJobResponse,
    TranscriptionJobStatusResponse,
)

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    404: {"model": ErrorResponse, "description": "Not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal error"},
}

router = APIRouter(prefix="/v1", tags=["v1"])


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        return

    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.get("/health", summary="Service health")
async def health(request: Request) -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "provider": settings.transcription_provider,
        "api_version": "v1",
        "request_id": request.state.request_id,
    }


def _enqueue(payload: TranscriptionJobRequest, background_tasks: BackgroundTasks) -> TranscriptionJobResponse:
    provider_name = payload.provider or settings.transcription_provider
    record = enqueue_job(source=payload.source, provider=provider_name)
    background_tasks.add_task(run_transcription_job, record.job_id)
    return TranscriptionJobResponse(job_id=record.job_id, status=record.status)


@router.post(
    "/transcribe",
    response_model=TranscriptionJobResponse,
    status_code=202,
    responses=ERROR_RESPONSES,
    summary="Enqueue transcription job",
)
async def transcribe(
    payload: TranscriptionJobRequest,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobResponse:
    return _enqueue(payload, background_tasks)


@router.post(
    "/intake",
    response_model=TranscriptionJobResponse,
    status_code=202,
    responses=ERROR_RESPONSES,
    summary="Upload file and enqueue job",
)
async def intake(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _auth: None = Depends(require_api_key),
) -> TranscriptionJobResponse:
    uploads_dir = Path("/srv/app/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)

    filename = Path(file.filename or "uploaded.bin").name
    target = uploads_dir / filename
    content = await file.read()
    target.write_bytes(content)

    payload = TranscriptionJobRequest(source=str(target), provider=settings.transcription_provider)
    return _enqueue(payload, background_tasks)


@router.get(
    "/job/{job_id}",
    response_model=TranscriptionJobStatusResponse,
    responses=ERROR_RESPONSES,
    summary="Get job status",
)
async def get_job(job_id: str, _auth: None = Depends(require_api_key)) -> TranscriptionJobStatusResponse:
    record = job_store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return to_job_status_response(record)

