import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import router as v1_router
from app.config import settings
from app.metrics import render_prometheus
from app.middleware.request_context import RequestContextMiddleware
from app.providers.factory import configure_provider_plugins
from app.providers.plugins import ProviderPluginError

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Container-first transcription API with queued processing and provider plugins.",
)
app.add_middleware(RequestContextMiddleware)


def _request_id(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    return rid or "unavailable"


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        404: "NOT_FOUND",
        422: "VALIDATION_ERROR",
    }
    payload = {
        "code": code_map.get(exc.status_code, "HTTP_ERROR"),
        "message": str(exc.detail),
        "details": exc.detail,
        "request_id": _request_id(request),
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    payload = {
        "code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "details": exc.errors(),
        "request_id": _request_id(request),
    }
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    payload = {
        "code": "INTERNAL_ERROR",
        "message": "Unexpected server error",
        "details": str(exc),
        "request_id": _request_id(request),
    }
    return JSONResponse(status_code=500, content=payload)


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
