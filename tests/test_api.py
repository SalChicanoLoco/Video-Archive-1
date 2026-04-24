import pytest

pytest.importorskip("fastapi")
pytest.importorskip("multipart")

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


def test_metrics_endpoint() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "app_requests_total" in text


def test_jobs_endpoints() -> None:
    response = client.post("/v1/transcribe", json={"source": "sample.mp4"})
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = client.get(f"/v1/job/{job_id}")
    assert status.status_code == 200

def test_error_contract_for_not_found() -> None:
    response = client.get("/v1/job/not-a-real-job-id")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert "message" in body
    assert "request_id" in body

def test_api_key_protection_when_enabled() -> None:
    original = settings.api_key
    settings.api_key = "supersecret"
    try:
        missing = client.post("/v1/transcribe", json={"source": "sample.mp4"})
        assert missing.status_code == 401
        missing_body = missing.json()
        assert missing_body["code"] == "UNAUTHORIZED"

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
