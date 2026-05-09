from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import request_context_middleware
from app.routers import themes, music
from app.routers import auth_router
from app.api.movies.router import router as phase2_movies_router


settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)

    app.include_router(themes.router)
    app.include_router(music.router)
    app.include_router(phase2_movies_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    app.include_router(auth_router)

    logger.info("app_started", extra={"event": "app_started"})
    return app


app = create_app()
