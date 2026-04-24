from __future__ import annotations

from typing import Protocol

from app.config import settings
from app.jobs.sqlite_store import SQLiteJobStore
from app.jobs.store import InMemoryJobStore, JobRecord
from app.providers.factory import UnsupportedProviderError, get_provider
from app.schemas.transcription import TranscriptionJobStatusResponse


class JobStore(Protocol):
    def create_job(self, source: str, provider: str) -> JobRecord: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[JobRecord]: ...

    def prune_jobs(self, keep_latest: int = 500) -> int: ...

    def set_status(
        self,
        job_id: str,
        status: str,
        result_text: str | None = None,
        error: str | None = None,
    ) -> JobRecord | None: ...


def _build_job_store() -> JobStore:
    if settings.job_store_backend == "sqlite":
        return SQLiteJobStore(settings.sqlite_db_path)
    return InMemoryJobStore()


def _airtable_log(event: str, payload: dict[str, str]) -> None:
    try:
        import airtable_client  # type: ignore

        airtable_client.log(event, payload)
    except Exception:
        return


def to_job_status_response(record: JobRecord) -> TranscriptionJobStatusResponse:
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


job_store: JobStore = _build_job_store()


def enqueue_job(source: str, provider: str) -> JobRecord:
    record = job_store.create_job(source=source, provider=provider)
    _airtable_log("job.created", {"job_id": record.job_id, "source": source, "provider": provider})
    return record


async def run_transcription_job(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if job is None:
        return

    job_store.set_status(job_id, status="running")
    _airtable_log("job.running", {"job_id": job_id})

    try:
        provider = get_provider(job.provider)
        result = await provider.transcribe(job.source)
        job_store.set_status(job_id, status="succeeded", result_text=result.text)
        _airtable_log("job.succeeded", {"job_id": job_id})
    except UnsupportedProviderError as exc:
        job_store.set_status(job_id, status="failed", error=str(exc))
        _airtable_log("job.failed", {"job_id": job_id, "reason": str(exc)})
    except Exception as exc:
        job_store.set_status(job_id, status="failed", error=str(exc))
        _airtable_log("job.failed", {"job_id": job_id, "reason": str(exc)})
