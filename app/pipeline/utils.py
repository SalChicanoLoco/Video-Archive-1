"""Shared path helpers for the pipeline. Enforces INPUT_DIR read-only guardrail."""
from __future__ import annotations

from pathlib import Path

from app.config import settings


def _input_dir() -> Path:
    return Path(settings.input_dir)


def _output_dir() -> Path:
    return Path(settings.output_dir)


def get_tape_output_dir(tape_id: str) -> Path:
    """Return (and create) OUTPUT_DIR/{tape_id}/."""
    d = _output_dir() / tape_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def guard_no_write_to_input(path: Path) -> None:
    """Raise ValueError if path resolves inside INPUT_DIR.

    Called before every write operation to enforce the read-only input guardrail
    at the code level (Docker also mounts the volume :ro).
    """
    try:
        path.resolve().relative_to(_input_dir().resolve())
    except ValueError:
        return  # path is NOT inside INPUT_DIR — safe to write
    raise ValueError(f"Refusing to write to read-only INPUT_DIR: {path}")


def get_input_file(filename: str) -> Path:
    """Return the path to a file in INPUT_DIR.

    Strips directory components to block path traversal, then checks the file
    exists. Raises ValueError on traversal attempt, FileNotFoundError if missing.
    """
    safe_name = Path(filename).name
    if safe_name != filename:
        raise ValueError(
            f"Path traversal blocked: {filename!r} contains directory components"
        )
    p = _input_dir() / safe_name
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    return p
