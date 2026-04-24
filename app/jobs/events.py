from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock


@dataclass
class JobEvent:
    job_id: str
    event: str
    timestamp: str
    detail: str | None = None


class JobEventStore:
    def __init__(self) -> None:
        self._events: list[JobEvent] = []
        self._lock = Lock()

    def add(self, job_id: str, event: str, detail: str | None = None) -> None:
        with self._lock:
            self._events.append(
                JobEvent(
                    job_id=job_id,
                    event=event,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    detail=detail,
                )
            )

    def for_job(self, job_id: str, limit: int = 100) -> list[JobEvent]:
        with self._lock:
            events = [e for e in self._events if e.job_id == job_id]
        return events[-limit:]


event_store = JobEventStore()
