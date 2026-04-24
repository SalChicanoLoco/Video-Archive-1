from fastapi import APIRouter, HTTPException

from app.config import settings
from app.providers.factory import (
    UnsupportedProviderError,
    get_provider,
    list_supported_providers,
)
from app.schemas.transcription import (
    ProvidersResponse,
    TranscriptionRequest,
    TranscriptionResponse,
)

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "provider": settings.transcription_provider,
        "api_version": "v1",
    }


@router.get("/providers", response_model=ProvidersResponse)
async def providers() -> ProvidersResponse:
    return ProvidersResponse(
        configured_provider=settings.transcription_provider,
        supported_providers=list_supported_providers(),
    )


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(payload: TranscriptionRequest) -> TranscriptionResponse:
    provider_name = payload.provider or settings.transcription_provider

    try:
        provider = get_provider(provider_name)
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await provider.transcribe(payload.source)
    return TranscriptionResponse(text=result.text, provider=result.provider)
