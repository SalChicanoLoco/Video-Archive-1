"""
Utility functions for the video processing pipeline.

This module centralises common helpers such as validating input paths,
generating standardised file names, ensuring directories exist and
formatting SRT timestamps. All functions operate relative to the
container's mounted volumes (/app/input and /app/output).
"""

import os
import uuid
from datetime import datetime
from pathlib import Path


# Define root directories for input and output. These can be
# overridden via environment variables for testing but default to
# locations defined in docker-compose volumes.
INPUT_ROOT = Path(os.getenv("INPUT_ROOT", "/app/input"))
OUTPUT_ROOT = Path(os.getenv("OUTPUT_ROOT", "/app/output"))


def ensure_dir(path: Path) -> None:
    """Create a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)


def validate_input_path(path: str, allow_output: bool = False) -> str:
    """Validate that the supplied path exists and resides within a safe directory.

    Args:
        path: Absolute path to validate.
        allow_output: If True, allow paths under OUTPUT_ROOT as well as
            INPUT_ROOT. This is useful for downstream steps that read
            intermediate files stored in the output directory (e.g. audio
            extraction returns a file in OUTPUT_ROOT).

    Returns:
        The normalised absolute path.

    Raises:
        ValueError: if the path is outside the permitted roots or does not
            exist.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise ValueError(f"File does not exist: {p}")
    allowed_roots = [INPUT_ROOT]
    if allow_output:
        allowed_roots.append(OUTPUT_ROOT)
    if not any(str(p).startswith(str(root.resolve())) for root in allowed_roots):
        raise ValueError(f"Path {p} is not within allowed directories: {allowed_roots}")
    return str(p)


def safe_filename(name: str) -> str:
    """Return a filesystem‑safe version of a filename.

    Removes or replaces characters that are problematic in POSIX
    filenames.
    """
    invalid = set('/\\?%*:|"<>')
    return ''.join('_' if c in invalid else c for c in name)


def generate_standard_name(original_path: str) -> str:
    """Generate a standardised new filename based on the original path and current date.

    The format is TAPE_UUID_YYYYMMDD.mp4 where UUID is a short unique
    identifier derived from the original filename. Location can be added
    externally if desired.
    """
    original_name = Path(original_path).stem
    date_str = datetime.utcnow().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:6].upper()
    return safe_filename(f"TAPE_{unique_id}_{date_str}.mp4")


def build_output_path(original_path: str, suffix: str) -> str:
    """Construct an output file path in OUTPUT_ROOT based on the input file name.

    Args:
        original_path: Absolute input file path.
        suffix: File extension including leading dot, e.g. '.wav' or '.srt'.

    Returns:
        Absolute path inside OUTPUT_ROOT.
    """
    input_name = Path(original_path).stem
    ensure_dir(OUTPUT_ROOT)
    return str(OUTPUT_ROOT / f"{input_name}{suffix}")