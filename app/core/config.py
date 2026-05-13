import os
from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = "My Life Movie API"
    service_name: str = "my-life-movie-backend"
    environment: str = "local"
    log_level: str = "INFO"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])
    database_url: str | None = None
    redis_url: str | None = None
    refresh_token_store: str = "mysql"
    refresh_token_redis_retention_seconds: int = 86_400
    refresh_token_expire_days: int = 14
    refresh_token_cookie_name: str = "refresh_token"
    refresh_token_cookie_path: str = "/auth"
    refresh_token_cookie_secure: bool = False
    refresh_token_cookie_samesite: str = "lax"
    access_token_secret_key: str = "local-dev-only-change-me-please-rotate"
    access_token_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    openai_api_key: str = ""
    video_generation_provider: str = "auto"
    generated_media_dir: str = "generated"
    openai_video_model: str = "sora-2"
    openai_video_size: str = "1280x720"
    openai_video_seconds: str = "4"
    openai_video_poll_interval_seconds: float = 10
    openai_video_max_wait_seconds: int = 900
    fal_key: str = ""
    fal_model_id: str = "fal-ai/wan-alpha"
    fal_queue_base_url: str = "https://queue.fal.run"
    fal_poll_interval_seconds: float = 5
    fal_max_wait_seconds: int = 900
    video_generation_worker_poll_interval_seconds: int = 5


def parse_csv_env(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default

    return [item.strip() for item in value.split(",") if item.strip()]


def parse_bool_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_int_env(value: str | None, default: int) -> int:
    if value is None:
        return default

    return int(value)


def parse_float_env(value: str | None, default: float) -> float:
    if value is None:
        return default

    return float(value)


@lru_cache
def get_settings() -> Settings:
    environment = os.getenv("APP_ENV", "local")
    secure_cookie_default = environment.lower() in {"prod", "production"}

    return Settings(
        environment=environment,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=parse_csv_env(
            os.getenv("CORS_ORIGINS"),
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        ),
        database_url=os.getenv("DATABASE_URL"),
        redis_url=os.getenv("REDIS_URL"),
        refresh_token_store=os.getenv("REFRESH_TOKEN_STORE", "mysql").strip().lower(),
        refresh_token_redis_retention_seconds=parse_int_env(
            os.getenv("REFRESH_TOKEN_REDIS_RETENTION_SECONDS"),
            86_400,
        ),
        refresh_token_expire_days=parse_int_env(
            os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"),
            14,
        ),
        refresh_token_cookie_secure=parse_bool_env(
            os.getenv("REFRESH_TOKEN_COOKIE_SECURE"),
            secure_cookie_default,
        ),
        access_token_secret_key=os.getenv(
            "ACCESS_TOKEN_SECRET_KEY",
            "local-dev-only-change-me-please-rotate",
        ),
        access_token_expire_minutes=parse_int_env(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"),
            15,
        ),
        spotify_client_id=os.getenv("SPOTIFY_CLIENT_ID", ""),
        spotify_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        video_generation_provider=os.getenv("VIDEO_GENERATION_PROVIDER", "auto").strip().lower(),
        generated_media_dir=os.getenv("GENERATED_MEDIA_DIR", "generated"),
        openai_video_model=os.getenv("OPENAI_VIDEO_MODEL", "sora-2"),
        openai_video_size=os.getenv("OPENAI_VIDEO_SIZE", "1280x720"),
        openai_video_seconds=os.getenv("OPENAI_VIDEO_SECONDS", "4"),
        openai_video_poll_interval_seconds=parse_float_env(
            os.getenv("OPENAI_VIDEO_POLL_INTERVAL_SECONDS"),
            10,
        ),
        openai_video_max_wait_seconds=parse_int_env(
            os.getenv("OPENAI_VIDEO_MAX_WAIT_SECONDS"),
            900,
        ),
        fal_key=os.getenv("FAL_KEY", ""),
        fal_model_id=os.getenv("FAL_MODEL_ID", "fal-ai/wan-alpha"),
        fal_queue_base_url=os.getenv("FAL_QUEUE_BASE_URL", "https://queue.fal.run").rstrip("/"),
        fal_poll_interval_seconds=parse_float_env(
            os.getenv("FAL_POLL_INTERVAL_SECONDS"),
            5,
        ),
        fal_max_wait_seconds=parse_int_env(
            os.getenv("FAL_MAX_WAIT_SECONDS"),
            900,
        ),
        video_generation_worker_poll_interval_seconds=parse_int_env(
            os.getenv("VIDEO_GENERATION_WORKER_POLL_INTERVAL_SECONDS"),
            5,
        ),
    )
