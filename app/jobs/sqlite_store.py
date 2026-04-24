from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import uuid4

from app.jobs.store import JobRecord


@dataclass
class SQLiteJobStore:
    db_path: str
    _lock: Lock = Lock()

    def __post_init__(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_text TEXT,
                    error TEXT
                )
                """
            )
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

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
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, source, provider, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.source,
                    record.provider,
                    record.status,
                    record.created_at,
                    record.updated_at,
                ),
            )
            conn.commit()
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, source, provider, status, created_at, updated_at, result_text, error
                FROM jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return JobRecord(
            job_id=row[0],
            source=row[1],
            provider=row[2],
            status=row[3],
            created_at=row[4],
            updated_at=row[5],
            result_text=row[6],
            error=row[7],
        )

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[JobRecord]:
        if status is not None:
            query = """
                SELECT job_id, source, provider, status, created_at, updated_at, result_text, error
                FROM jobs
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """
            params: tuple = (status, limit)
        else:
            query = """
                SELECT job_id, source, provider, status, created_at, updated_at, result_text, error
                FROM jobs
                ORDER BY updated_at DESC
                LIMIT ?
            """
            params = (limit,)

        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            JobRecord(
                job_id=row[0],
                source=row[1],
                provider=row[2],
                status=row[3],
                created_at=row[4],
                updated_at=row[5],
                result_text=row[6],
                error=row[7],
            )
            for row in rows
        ]

    def prune_jobs(self, keep_latest: int = 500) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                DELETE FROM jobs
                WHERE job_id NOT IN (
                    SELECT job_id FROM jobs ORDER BY updated_at DESC LIMIT ?
                )
                """,
                (keep_latest,),
            )
            conn.commit()
        return cursor.rowcount

    def set_status(
        self,
        job_id: str,
        status: str,
        result_text: str | None = None,
        error: str | None = None,
    ) -> JobRecord | None:
        updated_at = self._now()
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status = ?, result_text = ?, error = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, result_text, error, updated_at, job_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None

        return self.get_job(job_id)
