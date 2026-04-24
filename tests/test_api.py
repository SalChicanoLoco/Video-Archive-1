from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "provider" in body


def test_providers() -> None:
    response = client.get("/providers")
    assert response.status_code == 200
    body = response.json()
    assert "mock" in body["supported_providers"]


def test_transcribe_with_default_provider() -> None:
    response = client.post("/transcribe", json={"source": "sample.mp4"})
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert "sample.mp4" in body["text"]


def test_transcribe_with_unsupported_provider() -> None:
    response = client.post(
        "/transcribe",
        json={"source": "sample.mp4", "provider": "whisper"},
    )
    assert response.status_code == 400
    assert "intentionally not wired" in response.json()["detail"]
