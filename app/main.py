from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.movies.router import router as movies_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import request_context_middleware
from app.core.openapi import API_DESCRIPTION, OPENAPI_TAGS
from app.routers import themes, music
from app.routers import auth_router
from prometheus_fastapi_instrumentator import Instrumentator


settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        summary="My Life Movie 백엔드 API",
        description=API_DESCRIPTION,
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)
    Instrumentator().instrument(app).expose(app)
    Path(settings.generated_media_dir).mkdir(parents=True, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=settings.generated_media_dir), name="generated")

    app.include_router(themes.router)
    app.include_router(music.router)
    app.include_router(movies_router)
    app.include_router(auth_router)

    @app.get(
        "/health",
        tags=["시스템"],
        summary="헬스 체크",
        description="백엔드 애플리케이션이 요청을 처리할 수 있는지 확인합니다.",
    )
    async def health_check():
        return {"status": "ok"}

    logger.info("app_started", extra={"event": "app_started"})
    return app


app = create_app()
