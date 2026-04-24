from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["latest_api"] == "/v1"


def test_health_v1() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["api_version"] == "v1"


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
    assert "intentionally not wired" in response.json()["detail"]
