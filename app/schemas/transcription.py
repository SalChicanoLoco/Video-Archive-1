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


class TranscriptionJobRequest(BaseModel):
    source: str = Field(..., min_length=1)
    provider: str | None = None


class TranscriptionJobResponse(BaseModel):
    job_id: str
    status: str


class TranscriptionJobStatusResponse(BaseModel):
    job_id: str
    status: str
    source: str
    provider: str
    retry_count: int
    max_retries: int
    result_text: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class JobEventResponse(BaseModel):
    job_id: str
    event: str
    timestamp: str
    detail: str | None = None


class JobEventsListResponse(BaseModel):
    events: list[JobEventResponse]


class TranscriptionJobsListResponse(BaseModel):
    jobs: list[TranscriptionJobStatusResponse]


class JobsPruneResponse(BaseModel):
    deleted_count: int
