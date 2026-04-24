from fastapi import FastAPI, HTTPException

from app.config import settings
from app.providers.factory import UnsupportedProviderError, get_provider
from app.schemas.transcription import TranscriptionRequest, TranscriptionResponse

app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "provider": settings.transcription_provider,
    }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(payload: TranscriptionRequest) -> TranscriptionResponse:
    try:
        provider = get_provider(settings.transcription_provider)
    except UnsupportedProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = await provider.transcribe(payload.source)
    return TranscriptionResponse(text=result.text, provider=result.provider)
