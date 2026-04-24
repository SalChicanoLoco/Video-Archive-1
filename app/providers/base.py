from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class TranscriptResult:
    text: str
    provider: str


class TranscriptionProvider(ABC):
    """Provider contract for transcription backends."""

    name: str

    @abstractmethod
    async def transcribe(self, source: str) -> TranscriptResult:
        """Transcribe source input and return normalized result."""
