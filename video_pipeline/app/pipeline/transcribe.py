"""
Transcription module using faster‑whisper.

The faster‑whisper library is a CPU‑optimised implementation of
Whisper that uses CTranslate2 for efficient inference. It exposes a
``WhisperModel`` class with a ``transcribe`` method accepting options
like ``beam_size`` and voice activity detection (VAD) filtering【904580658027665†L227-L239】【904580658027665†L303-L320】. This module wraps
that functionality and converts the transcription into SRT subtitles
using the `srt` library.
"""

from datetime import timedelta
from pathlib import Path
from typing import Iterable, Optional

import srt

from . import utils


def _to_timedelta(seconds: float) -> timedelta:
    """Convert a floating‑point time in seconds to a timedelta."""
    return timedelta(seconds=seconds)


def transcribe_audio(
    audio_path: str,
    model,
    beam_size: int = 5,
    vad_filter: bool = True,
    word_timestamps: bool = False,
) -> str:
    """Transcribe an audio file and write an SRT subtitle file.

    Args:
        audio_path: Absolute path to an audio file (wav or mp3).
        model: A preloaded faster_whisper.WhisperModel instance.
        beam_size: Beam search width controlling accuracy versus speed.
        vad_filter: Whether to apply voice activity detection【904580658027665†L303-L320】.
        word_timestamps: Whether to include word‑level timestamps.

    Returns:
        Absolute path to the generated SRT file within OUTPUT_ROOT.
    """
    src = Path(audio_path).resolve()
    utils.validate_input_path(str(src), allow_output=True)
    # Determine output file path
    out_path = Path(utils.build_output_path(str(src), ".srt"))
    # Run transcription
    segments, info = model.transcribe(
        str(src),
        beam_size=beam_size,
        vad_filter=vad_filter,
        word_timestamps=word_timestamps,
    )
    subtitles = []
    index = 1
    for seg in segments:
        start_td = _to_timedelta(seg.start)
        end_td = _to_timedelta(seg.end)
        subtitles.append(srt.Subtitle(index=index, start=start_td, end=end_td, content=seg.text.strip()))
        index += 1
    srt_data = srt.compose(subtitles)
    # Ensure output directory exists
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(srt_data, encoding="utf-8")
    return str(out_path)