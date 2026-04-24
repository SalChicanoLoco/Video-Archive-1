from __future__ import annotations

import importlib
from collections.abc import Callable

from app.providers.base import TranscriptionProvider


class ProviderPluginError(ValueError):
    pass


def parse_plugin_specs(specs: str | None) -> list[tuple[str, str, str]]:
    """Parse comma-separated plugin specs: name=module.path:ClassName."""
    if not specs:
        return []

    parsed: list[tuple[str, str, str]] = []
    for raw in specs.split(","):
        item = raw.strip()
        if not item:
            continue

        if "=" not in item:
            raise ProviderPluginError(
                f"Invalid plugin spec '{item}'. Expected format: name=module.path:ClassName"
            )

        name, import_ref = item.split("=", 1)
        if ":" not in import_ref:
            raise ProviderPluginError(
                f"Invalid plugin import '{import_ref}'. Expected module.path:ClassName"
            )

        module_name, class_name = import_ref.split(":", 1)
        parsed.append((name.strip().lower(), module_name.strip(), class_name.strip()))

    return parsed


def load_plugin_provider_factory(module_name: str, class_name: str) -> Callable[[], TranscriptionProvider]:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise ProviderPluginError(
            f"Plugin module '{module_name}' not found"
        ) from exc

    cls = getattr(module, class_name, None)
    if cls is None:
        raise ProviderPluginError(
            f"Plugin class '{class_name}' not found in module '{module_name}'"
        )

    if not isinstance(cls, type) or not issubclass(cls, TranscriptionProvider):
        raise ProviderPluginError(
            f"Plugin class '{module_name}:{class_name}' must inherit TranscriptionProvider"
        )

    def factory() -> TranscriptionProvider:
        return cls()

    return factory
