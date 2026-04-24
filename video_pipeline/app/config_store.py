"""
Runtime config store: fetches sensitive keys from Airtable.

The only credential that needs to be in .env (or entered via /setup) is
AIRTABLE_API_KEY. Everything else — including ANTHROPIC_API_KEY — lives
in an Airtable "Config" table and is pulled at runtime.

This means the USB stick never carries Mark's Anthropic key. If Airtable
is unreachable, the pipeline degrades gracefully to SRT-only mode.

Airtable "Config" table structure (create this in your base):
  Key   (Single line text)  — e.g. "ANTHROPIC_API_KEY"
  Value (Single line text)  — the actual value

On the USB stick, .env only needs:
  AIRTABLE_API_KEY=pat...
  AIRTABLE_BASE_ID=app...
"""

from __future__ import annotations

import logging
import os
from threading import Lock

logger = logging.getLogger("pipeline.config_store")

_lock = Lock()
_cache: dict[str, str] = {}
_airtable_ok: bool = False
_loaded: bool = False

# Name of the table in your Airtable base that holds key/value config
_CONFIG_TABLE = os.getenv("AIRTABLE_CONFIG_TABLE", "Config")


def _airtable_key() -> str:
    return os.getenv("AIRTABLE_API_KEY", "")


def _base_id() -> str:
    return os.getenv("AIRTABLE_BASE_ID", "")


def load(airtable_api_key: str = "", base_id: str = "") -> dict[str, str]:
    """Pull key/value pairs from the Airtable Config table.

    Uses provided credentials first, then falls back to env vars.
    Returns empty dict and logs a warning on any failure — never raises.
    """
    global _cache, _airtable_ok, _loaded

    api_key = airtable_api_key or _airtable_key()
    bid = base_id or _base_id()

    if not api_key or not bid:
        logger.warning(
            "Airtable not configured (missing AIRTABLE_API_KEY or AIRTABLE_BASE_ID) "
            "— running in SRT-only mode"
        )
        with _lock:
            _airtable_ok = False
            _loaded = True
        return {}

    try:
        from pyairtable import Api
        table = Api(api_key).base(bid).table(_CONFIG_TABLE)
        records = table.all()
        config: dict[str, str] = {}
        for r in records:
            k = r["fields"].get("Key", "").strip()
            v = r["fields"].get("Value", "").strip()
            if k:
                config[k] = v

        with _lock:
            _cache = config
            _airtable_ok = True
            _loaded = True

        logger.info("Loaded %d config value(s) from Airtable (%s)", len(config), _CONFIG_TABLE)
        return config

    except Exception as exc:
        logger.warning("Could not load config from Airtable: %s — SRT-only mode", exc)
        with _lock:
            _airtable_ok = False
            _loaded = True
        return {}


def reload() -> dict[str, str]:
    """Force a fresh fetch from Airtable."""
    global _loaded
    with _lock:
        _loaded = False
    return load()


def get(key: str, default: str = "") -> str:
    """Return a config value.

    Checks (in order):
      1. Airtable cache (loaded at startup)
      2. Environment variable
      3. Provided default
    """
    global _loaded
    if not _loaded:
        load()
    with _lock:
        return _cache.get(key) or os.getenv(key, default)


def status() -> dict:
    """Return a safe status dict for the /setup UI (no secret values exposed)."""
    global _loaded
    if not _loaded:
        load()
    with _lock:
        has_anthropic = bool(_cache.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
        config_keys = [k for k in _cache if k != "ANTHROPIC_API_KEY"]
        return {
            "airtable_connected": _airtable_ok,
            "airtable_base_id": _base_id() or "(not set)",
            "anthropic_key_available": has_anthropic,
            "edl_enabled": has_anthropic,
            "config_keys_found": config_keys,
            "config_table": _CONFIG_TABLE,
        }
