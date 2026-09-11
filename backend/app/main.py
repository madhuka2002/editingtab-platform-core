from fastapi import FastAPI

from app.api.v1.health import router as health_router
from app.core.config import settings


def create_application() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.include_router(
        health_router,
        prefix=settings.api_v1_prefix,
    )

    return application


app = create_application()