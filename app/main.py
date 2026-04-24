import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as v1_router
from app.config import settings
from app.metrics import render_prometheus
from app.middleware.request_context import RequestContextMiddleware
from app.providers.factory import configure_provider_plugins
from app.providers.plugins import ProviderPluginError
from app.schemas.errors import ErrorResponse

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


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    body = ErrorResponse(
        code=f"HTTP_{exc.status_code}",
        message=str(exc.detail),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return render_prometheus()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")
