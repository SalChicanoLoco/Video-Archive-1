import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as v1_router
from app.config import settings
from app.metrics import render_prometheus
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

static_dir = Path("app/static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(v1_router)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(render_prometheus(), media_type="text/plain; version=0.0.4")
