from __future__ import annotations

from typing import Protocol

from app.config import settings
from app.jobs.sqlite_store import SQLiteJobStore
from app.jobs.store import InMemoryJobStore, JobRecord
from app.providers.factory import UnsupportedProviderError, get_provider


class JobStore(Protocol):
    def create_job(self, source: str, provider: str) -> JobRecord: ...

    def get_job(self, job_id: str) -> JobRecord | None: ...

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


job_store: JobStore = _build_job_store()


async def run_transcription_job(job_id: str) -> None:
    job = job_store.get_job(job_id)
    if job is None:
        return

    job_store.set_status(job_id, status="running")

    try:
        provider = get_provider(job.provider)
        result = await provider.transcribe(job.source)
        job_store.set_status(job_id, status="succeeded", result_text=result.text)
    except UnsupportedProviderError as exc:
        job_store.set_status(job_id, status="failed", error=str(exc))
    except Exception as exc:  # defensive catch for background task stability
        job_store.set_status(job_id, status="failed", error=str(exc))
