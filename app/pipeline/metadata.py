"""
Metadata embedding module.

Uses ffmpeg to embed metadata tags into a video without re‑encoding the
streams. The TecMint article shows how to update video metadata using
the ``-metadata`` flag and ``-codec copy`` to avoid re‑encoding,
preserving quality【545890140196842†L143-L175】.
"""

import os
import shutil
import subprocess
from pathlib import Path

from . import utils


def embed_metadata(path: str, title: str, date: str, comment: str) -> str:
    """Embed metadata into a video file using ffmpeg.

    The function writes to a temporary file in the same directory,
    preserving the original file until ffmpeg succeeds. If the
    operation is successful, the original file is replaced. Metadata
    fields left empty will be omitted.

    Args:
        path: Absolute path to an existing video file.
        title: Title to embed (maps to ``-metadata title``).
        date: Creation time (maps to ``-metadata creation_time``).
        comment: Comment field (maps to ``-metadata comment``).

    Returns:
        Absolute path of the file with embedded metadata (same as input).
    """
    src = Path(path).resolve()
    utils.validate_input_path(str(src))
    temp_file = src.with_suffix('.tmp' + src.suffix)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src),
    ]
    # Add metadata options only for non-empty fields
    if title:
        cmd += ["-metadata", f"title={title}"]
    if date:
        cmd += ["-metadata", f"creation_time={date}"]
    if comment:
        cmd += ["-metadata", f"comment={comment}"]
    cmd += ["-codec", "copy", str(temp_file)]
    # Execute the command
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")
    # Replace the original file atomically
    temp_file.replace(src)
    return str(src)