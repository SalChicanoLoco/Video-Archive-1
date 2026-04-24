from pathlib import Path

from app.jobs.sqlite_store import SQLiteJobStore


def test_sqlite_store_create_and_update(tmp_path: Path) -> None:
    db_file = tmp_path / "jobs.db"
    store = SQLiteJobStore(str(db_file))

    created = store.create_job(source="video.mp4", provider="mock")
    assert created.status == "queued"

    loaded = store.get_job(created.job_id)
    assert loaded is not None
    assert loaded.source == "video.mp4"

    listed = store.list_jobs()
    assert len(listed) == 1

    updated = store.set_status(created.job_id, status="succeeded", result_text="ok")
    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.result_text == "ok"
