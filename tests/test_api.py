import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_api"] == "/v1"
    assert "request_id" in body
    assert response.headers["X-Request-ID"] == body["request_id"]


def test_health_v1() -> None:
    response = client.get("/v1/health", headers={"x-request-id": "req-123"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "v1"
    assert body["request_id"] == "req-123"
    assert response.headers["X-Request-ID"] == "req-123"


def test_providers_v1() -> None:
    response = client.get("/v1/providers")
    assert response.status_code == 200
    body = response.json()
    assert "mock" in body["supported_providers"]


def test_transcribe_with_default_provider_v1() -> None:
    response = client.post("/v1/transcribe", json={"source": "sample.mp4"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert "sample.mp4" in body["text"]


def test_transcribe_with_unsupported_provider_v1() -> None:
    response = client.post(
        "/v1/transcribe",
        json={"source": "sample.mp4", "provider": "whisper"},
    )
    assert response.status_code == 400
    assert "PROVIDER_PLUGINS" in response.json()["detail"]


def test_job_flow_transcription_v1() -> None:
    enqueue = client.post("/v1/jobs/transcribe", json={"source": "queued.mp4"})
    assert enqueue.status_code == 202
    job_id = enqueue.json()["job_id"]

    status = client.get(f"/v1/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["job_id"] == job_id
    assert body["status"] in {"queued", "running", "succeeded"}
