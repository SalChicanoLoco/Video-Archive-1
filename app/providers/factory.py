from __future__ import annotations

from collections.abc import Callable

from app.providers.base import TranscriptionProvider
from app.providers.mock import MockTranscriptionProvider
from app.providers.plugins import (
    ProviderPluginError,
    load_plugin_provider_factory,
    parse_plugin_specs,
)


class UnsupportedProviderError(ValueError):
    pass


_PROVIDER_REGISTRY: dict[str, Callable[[], TranscriptionProvider]] = {
    "mock": MockTranscriptionProvider,
}


def register_provider(name: str, factory: Callable[[], TranscriptionProvider]) -> None:
    normalized = name.strip().lower()
    if not normalized:
        raise ProviderPluginError("Provider name cannot be empty")

    if normalized in _PROVIDER_REGISTRY:
        raise ProviderPluginError(f"Provider '{normalized}' is already registered")

    _PROVIDER_REGISTRY[normalized] = factory


def configure_provider_plugins(specs: str | None) -> None:
    for name, module_name, class_name in parse_plugin_specs(specs):
        factory = load_plugin_provider_factory(module_name, class_name)
        register_provider(name, factory)


def list_supported_providers() -> list[str]:
    return sorted(_PROVIDER_REGISTRY.keys())


def get_provider(provider_name: str | None) -> TranscriptionProvider:
    normalized = (provider_name or "mock").strip().lower()

    if normalized in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[normalized]()

    if normalized == "whisper":
        raise UnsupportedProviderError(
            "'whisper' provider is not registered. "
            "Add a plugin via PROVIDER_PLUGINS (e.g. whisper=your.module:WhisperProvider)."
        )

    supported = ", ".join(list_supported_providers())
    raise UnsupportedProviderError(
        f"Unsupported provider '{normalized}'. Supported: {supported}"
    )
