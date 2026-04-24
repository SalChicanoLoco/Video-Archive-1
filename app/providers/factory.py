from __future__ import annotations

from collections.abc import Callable

from app.providers.base import TranscriptionProvider
from app.providers.mock import MockTranscriptionProvider


class UnsupportedProviderError(ValueError):
    pass


_PROVIDER_REGISTRY: dict[str, Callable[[], TranscriptionProvider]] = {
    "mock": MockTranscriptionProvider,
}


def list_supported_providers() -> list[str]:
    return sorted(_PROVIDER_REGISTRY.keys())


def get_provider(provider_name: str | None) -> TranscriptionProvider:
    normalized = (provider_name or "mock").strip().lower()

    if normalized in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[normalized]()

    if normalized == "whisper":
        raise UnsupportedProviderError(
            "'whisper' provider is intentionally not wired in this scaffold. "
            "Keep TRANSCRIPTION_PROVIDER=mock unless you add an adapter."
        )

    supported = ", ".join(list_supported_providers())
    raise UnsupportedProviderError(
        f"Unsupported provider '{normalized}'. Supported: {supported}"
    )
