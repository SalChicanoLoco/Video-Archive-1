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
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    max_retries INTEGER NOT NULL DEFAULT 0,
                    result_text TEXT,
                    error TEXT
                )
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            if "retry_count" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")
            if "max_retries" not in columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(self, source: str, provider: str, max_retries: int) -> JobRecord:
        now = self._now()
        record = JobRecord(
            job_id=str(uuid4()),
            source=source,
            provider=provider,
            status="queued",
            created_at=now,
            updated_at=now,
            retry_count=0,
            max_retries=max_retries,
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, source, provider, status, created_at, updated_at, retry_count, max_retries
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.job_id,
                    record.source,
                    record.provider,
                    record.status,
                    record.created_at,
                    record.updated_at,
                    record.retry_count,
                    record.max_retries,
                ),
            )
            conn.commit()
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, source, provider, status, created_at, updated_at,
                       retry_count, max_retries, result_text, error
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
            retry_count=row[6],
            max_retries=row[7],
            result_text=row[8],
            error=row[9],
        )

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[JobRecord]:
        query = """
            SELECT job_id, source, provider, status, created_at, updated_at,
                   retry_count, max_retries, result_text, error
            FROM jobs
        """
        params: tuple[object, ...]
        if status:
            query += " WHERE status = ?"
            query += " ORDER BY updated_at DESC LIMIT ?"
            params = (status, limit)
        else:
            query += " ORDER BY updated_at DESC LIMIT ?"
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
                retry_count=row[6],
                max_retries=row[7],
                result_text=row[8],
                error=row[9],
            )
            for row in rows
        ]

    def prune_jobs(self, keep_latest: int = 500) -> int:
        with self._lock, self._connect() as conn:
            to_delete = conn.execute(
                """
                SELECT job_id FROM jobs
                ORDER BY updated_at DESC
                LIMIT -1 OFFSET ?
                """,
                (keep_latest,),
            ).fetchall()
            delete_count = len(to_delete)
            if delete_count:
                conn.executemany("DELETE FROM jobs WHERE job_id = ?", to_delete)
                conn.commit()
            return delete_count

    def set_status(
        self,
        job_id: str,
        status: str,
        result_text: str | None = None,
        error: str | None = None,
        retry_count: int | None = None,
    ) -> JobRecord | None:
        updated_at = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, result_text = ?, error = ?, updated_at = ?,
                    retry_count = COALESCE(?, retry_count)
                WHERE job_id = ?
                """,
                (status, result_text, error, updated_at, retry_count, job_id),
            )
            conn.commit()

        return self.get_job(job_id)
