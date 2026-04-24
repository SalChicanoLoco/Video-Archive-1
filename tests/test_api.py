import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.config import settings
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
