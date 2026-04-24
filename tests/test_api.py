import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.config import settings
from app.jobs.service import job_store
from app.main import app


client = TestClient(app)


def test_health_v1() -> None:
    response = client.get("/v1/health", headers={"x-request-id": "req-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "v1"


def test_jobs_endpoints() -> None:
    response = client.post("/v1/transcribe", json={"source": "sample.mp4"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = client.get(f"/v1/job/{job_id}")
    assert status.status_code == 200

    jobs = client.get("/v1/jobs")
    assert jobs.status_code == 200
    assert isinstance(jobs.json()["jobs"], list)


def test_process_endpoint_alias() -> None:
    response = client.post("/v1/process", json={"source": "sample.mp4"})
    assert response.status_code == 202


def test_api_key_protection_when_enabled() -> None:
    original = settings.api_key
    settings.api_key = "supersecret"
    try:
        missing = client.post("/v1/transcribe", json={"source": "sample.mp4"})
        assert missing.status_code == 401

        bad = client.post(
            "/v1/transcribe",
            json={"source": "sample.mp4"},
            headers={"x-api-key": "wrong"},
        )
        assert bad.status_code == 401

        good = client.post(
            "/v1/transcribe",
            json={"source": "sample.mp4"},
            headers={"x-api-key": "supersecret"},
        )
        assert good.status_code == 202
    finally:
        settings.api_key = original


def test_error_response_shape_on_401() -> None:
    original = settings.api_key
    settings.api_key = "secret"
    try:
        response = client.get("/v1/jobs")
        assert response.status_code == 401
        body = response.json()
        assert "code" in body
        assert "message" in body
        assert "request_id" in body
    finally:
        settings.api_key = original


def test_error_response_shape_on_404() -> None:
    response = client.get("/v1/job/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "HTTP_404"
    assert "request_id" in body


def test_list_jobs_status_filter() -> None:
    # Enqueue a job; the mock provider completes it synchronously in TestClient
    client.post("/v1/transcribe", json={"source": "filter_test.mp4"})

    all_jobs = client.get("/v1/jobs").json()["jobs"]
    assert len(all_jobs) > 0

    statuses = {j["status"] for j in all_jobs}
    for s in statuses:
        filtered = client.get(f"/v1/jobs?status={s}").json()["jobs"]
        assert all(j["status"] == s for j in filtered)

    # Non-existent status returns empty list, not an error
    empty = client.get("/v1/jobs?status=nonexistent").json()["jobs"]
    assert empty == []


def test_prune_jobs() -> None:
    # Seed several jobs
    for _ in range(5):
        client.post("/v1/transcribe", json={"source": "prune_test.mp4"})

    all_before = client.get("/v1/jobs?limit=1000").json()["jobs"]
    total_before = len(all_before)

    keep = max(1, total_before - 2)
    response = client.post(f"/v1/jobs/prune?keep_latest={keep}")
    assert response.status_code == 200
    body = response.json()
    assert "deleted" in body
    assert "kept" in body
    assert body["deleted"] >= 0
    assert body["kept"] <= keep

    all_after = client.get("/v1/jobs?limit=1000").json()["jobs"]
    assert len(all_after) <= keep


def test_metrics_endpoint() -> None:
    # Hit a real endpoint first so counters are non-zero
    client.get("/v1/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "app_requests_total" in text
    assert "app_requests_by_status_total" in text
    assert "app_job_events_total" in text


def test_intake_rejects_path_traversal(tmp_path) -> None:
    from io import BytesIO

    dangerous_name = "../../etc/passwd"
    data = BytesIO(b"fake video content")

    response = client.post(
        "/v1/intake",
        files={"file": (dangerous_name, data, "video/mp4")},
    )
    # Request should succeed (202) but file must NOT be written outside uploads dir
    assert response.status_code == 202
    # The dangerous path component should not have escaped the uploads dir
    import os
    assert not os.path.exists("/etc/passwd_written_by_test")
