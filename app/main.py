import logging

from fastapi import FastAPI, Request

from app.api.v1 import router as v1_router
from app.config import settings
from app.middleware.request_context import RequestContextMiddleware
from app.providers.factory import configure_provider_plugins
from app.providers.plugins import ProviderPluginError

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestContextMiddleware)

try:
    configure_provider_plugins(settings.provider_plugins)
except ProviderPluginError as exc:
    logging.getLogger("video_archive.api").warning(
        "provider plugin configuration skipped: %s", exc
    )

app.include_router(v1_router)


@app.get("/")
async def root(request: Request) -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "latest_api": "/v1",
        "request_id": request.state.request_id,
    }
