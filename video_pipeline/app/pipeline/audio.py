"""
Audio extraction module.

Provides a function to extract the audio track from a video file using
ffmpeg. Following examples from tinyapps.org and UnderHost, we use
``-vn`` to ignore the video stream and ``-acodec copy`` or a PCM
codec to avoid re‑encoding【165115472084467†L9-L16】【308060662158292†L216-L219】.
"""

import subprocess
from pathlib import Path

from . import utils


def extract_audio(path: str, fmt: str = "wav") -> str:
    """Extract the audio track from a video file.

    Args:
        path: Absolute path to a video file.
        fmt: Desired audio format ("wav" or "mp3"). Defaults to
            lossless WAV. If MP3 is chosen, a high quality setting is used.

    Returns:
        Absolute path to the extracted audio file within OUTPUT_ROOT.
    """
    src = Path(path).resolve()
    utils.validate_input_path(str(src), allow_output=True)
    # Determine output file path
    suffix = ".wav" if fmt.lower() == "wav" else ".mp3"
    out_path = Path(utils.build_output_path(str(src), suffix))
    # Build ffmpeg command
    if fmt.lower() == "wav":
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-acodec",
            "pcm_s16le",
            str(out_path),
        ]
    else:
        # MP3 extraction; use -q:a 0 for highest quality MP3【308060662158292†L216-L219】
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-vn",
            "-q:a",
            "0",
            "-map",
            "a",
            str(out_path),
        ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr}")
    return str(out_path)