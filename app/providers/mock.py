from __future__ import annotations

from app.providers.base import TranscriptResult, TranscriptionProvider


class MockTranscriptionProvider(TranscriptionProvider):
    """Default provider: no external API calls required."""

    name = "mock"

    async def transcribe(self, source: str) -> TranscriptResult:
        return TranscriptResult(
            text=f"[mock transcript] processed source='{source}'",
            provider=self.name,
        )
