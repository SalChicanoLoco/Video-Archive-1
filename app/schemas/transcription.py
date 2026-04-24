from pydantic import BaseModel, Field


class TranscriptionRequest(BaseModel):
    source: str = Field(
        ...,
        min_length=1,
        description="Path, URL, or opaque source identifier",
    )
    provider: str | None = Field(
        default=None,
        description="Optional request-level provider override",
    )


class TranscriptionResponse(BaseModel):
    text: str
    provider: str


class ProvidersResponse(BaseModel):
    configured_provider: str
    supported_providers: list[str]
