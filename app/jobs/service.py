from __future__ import annotations

import asyncio
from typing import Protocol

from app.config import settings
from app.jobs.events import event_store
from app.jobs.sqlite_store import SQLiteJobStore
from app.jobs.store import InMemoryJobStore, JobRecord
from app.metrics import inc_job_event
from app.providers.factory import UnsupportedProviderError, get_provider
from app.schemas.transcription import TranscriptionJobStatusResponse


class JobStore(Protocol):
    def create_job(self, source: str, provider: str, max_retries: int) -> JobRecord: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[JobRecord]: ...

    def prune_jobs(self, keep_latest: int = 500) -> int: ...

    def set_status(
        self,
        job_id: str,
        status: str,
        result_text: str | None = None,
        error: str | None = None,
        retry_count: int | None = None,
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


def _log_event(job_id: str, event: str, detail: str | None = None) -> None:
    event_store.add(job_id=job_id, event=event, detail=detail)
    inc_job_event(event)


def to_job_status_response(record: JobRecord) -> TranscriptionJobStatusResponse:
    return TranscriptionJobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        source=record.source,
        provider=record.provider,
        retry_count=record.retry_count,
        max_retries=record.max_retries,
        result_text=record.result_text,
        error=record.error,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


job_store: JobStore = _build_job_store()


def enqueue_job(source: str, provider: str) -> JobRecord:
    record = job_store.create_job(
        source=source,
        provider=provider,
        max_retries=settings.max_retries,
    )
    _log_event(record.job_id, "created")
    _airtable_log("job.created", {"job_id": record.job_id, "source": source, "provider": provider})
    return record


async def run_transcription_job(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if job is None:
        return

    while True:
        job_store.set_status(job_id, status="running", retry_count=job.retry_count)
        _log_event(job_id, "running")
        _airtable_log("job.running", {"job_id": job_id, "retry_count": str(job.retry_count)})

        try:
            provider = get_provider(job.provider)
            result = await provider.transcribe(job.source)
            job_store.set_status(job_id, status="succeeded", result_text=result.text, retry_count=job.retry_count)
            _log_event(job_id, "succeeded")
            _airtable_log("job.succeeded", {"job_id": job_id})
            return
        except UnsupportedProviderError as exc:
            job_store.set_status(job_id, status="failed", error=str(exc), retry_count=job.retry_count)
            _log_event(job_id, "failed", detail=str(exc))
            _airtable_log("job.failed", {"job_id": job_id, "reason": str(exc)})
            return
        except Exception as exc:
            if job.retry_count < job.max_retries:
                next_retry = job.retry_count + 1
                backoff = settings.retry_backoff_seconds * (2 ** (next_retry - 1))
                job_store.set_status(
                    job_id,
                    status="retrying",
                    error=str(exc),
                    retry_count=next_retry,
                )
                _log_event(job_id, "retrying", detail=f"retry={next_retry},backoff={backoff}")
                _airtable_log(
                    "job.retrying",
                    {"job_id": job_id, "retry_count": str(next_retry), "backoff_seconds": str(backoff)},
                )
                await asyncio.sleep(backoff)
                job = job_store.get_job(job_id)
                if job is None:
                    return
                continue

            job_store.set_status(job_id, status="failed", error=str(exc), retry_count=job.retry_count)
            _log_event(job_id, "failed", detail=str(exc))
            _airtable_log("job.failed", {"job_id": job_id, "reason": str(exc)})
            return
