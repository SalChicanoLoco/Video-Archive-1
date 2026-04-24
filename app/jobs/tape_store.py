"""In-memory store for tape-specific background jobs and batch records."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TapeJob:
    job_id: str
    tape_id: str
    operation: str   # extract_audio | transcribe | generate_edl
    status: str      # queued | running | succeeded | failed
    started: str
    updated: str
    result: dict | None = None
    error: str | None = None


@dataclass
class BatchRecord:
    batch_id: str
    tape_ids: list[str]
    operations: list[str]
    created: str
    job_ids: list[str] = field(default_factory=list)


class TapeJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, TapeJob] = {}
        self._lock = Lock()

    def create(self, tape_id: str, operation: str) -> TapeJob:
        now = _now()
        job = TapeJob(
            job_id=str(uuid4()),
            tape_id=tape_id,
            operation=operation,
            status="queued",
            started=now,
            updated=now,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> TapeJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def set_running(self, job_id: str) -> None:
        with self._lock:
            if j := self._jobs.get(job_id):
                j.status = "running"
                j.updated = _now()

    def set_succeeded(self, job_id: str, result: dict | None = None) -> None:
        with self._lock:
            if j := self._jobs.get(job_id):
                j.status = "succeeded"
                j.result = result or {}
                j.updated = _now()

    def set_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            if j := self._jobs.get(job_id):
                j.status = "failed"
                j.error = error
                j.updated = _now()

    def list_for_tape(self, tape_id: str) -> list[TapeJob]:
        with self._lock:
            return [j for j in self._jobs.values() if j.tape_id == tape_id]


tape_job_store = TapeJobStore()
batch_store: dict[str, BatchRecord] = {}
