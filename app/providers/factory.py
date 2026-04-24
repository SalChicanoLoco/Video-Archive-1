from __future__ import annotations

from app.providers.base import TranscriptionProvider
from app.providers.mock import MockTranscriptionProvider


class UnsupportedProviderError(ValueError):
    pass


def get_provider(provider_name: str | None) -> TranscriptionProvider:
    normalized = (provider_name or "mock").strip().lower()

    if normalized == "mock":
        return MockTranscriptionProvider()

    if normalized == "whisper":
        raise UnsupportedProviderError(
            "'whisper' provider is intentionally not wired in this scaffold. "
            "Keep TRANSCRIPTION_PROVIDER=mock unless you add an adapter."
        )

    raise UnsupportedProviderError(
        f"Unsupported provider '{normalized}'. Supported: mock"
    )
