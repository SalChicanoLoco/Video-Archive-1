from __future__ import annotations

from app.jobs.store import InMemoryJobStore
from app.providers.factory import UnsupportedProviderError, get_provider

job_store = InMemoryJobStore()


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
