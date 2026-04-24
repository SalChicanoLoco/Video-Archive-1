from fastapi import FastAPI

from app.api.v1 import router as v1_router
from app.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(v1_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "ok",
        "latest_api": "/v1",
    }
