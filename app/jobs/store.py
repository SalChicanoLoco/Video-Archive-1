from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


@dataclass
class JobRecord:
    job_id: str
    source: str
    provider: str
    status: str
    created_at: str
    updated_at: str
    result_text: str | None = None
    error: str | None = None


@dataclass
class InMemoryJobStore:
    _jobs: dict[str, JobRecord] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, source: str, provider: str) -> JobRecord:
        now = self._now()
        record = JobRecord(
            job_id=str(uuid4()),
            source=source,
            provider=provider,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._jobs[record.job_id] = record
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[JobRecord]:
        with self._lock:
            jobs = list(self._jobs.values())
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda x: x.updated_at, reverse=True)
        return jobs[:limit]

    def prune_jobs(self, keep_latest: int = 500) -> int:
        with self._lock:
            ordered = sorted(self._jobs.values(), key=lambda x: x.updated_at, reverse=True)
            to_delete = [j.job_id for j in ordered[keep_latest:]]
            for job_id in to_delete:
                del self._jobs[job_id]
        return len(to_delete)

    def set_status(
        self,
        job_id: str,
        status: str,
        result_text: str | None = None,
        error: str | None = None,
    ) -> JobRecord | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            record.status = status
            record.result_text = result_text
            record.error = error
            record.updated_at = self._now()
            return record
