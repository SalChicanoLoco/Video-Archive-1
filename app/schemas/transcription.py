from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    source: str = Field(..., description="Path, URL, or opaque source identifier")


class TranscriptionResponse(BaseModel):
    text: str
    provider: str
