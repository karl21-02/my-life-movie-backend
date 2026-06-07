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
    openai_chat_model: str = "gpt-4o-mini"
    openai_chat_timeout_seconds: float = 10.0
    openai_chat_max_tokens: int = 250
    openai_story_finalize_timeout_seconds: float = 45.0
    openai_story_finalize_max_tokens: int = 900
    video_generation_provider: str = "auto"
    generated_media_dir: str = "generated"
    openai_video_model: str = "sora-2"
    openai_video_size: str = "1280x720"
    openai_video_seconds: str = "8"
    openai_video_poll_interval_seconds: float = 10
    openai_video_max_wait_seconds: int = 900
    fal_key: str = ""
    fal_model_id: str = "fal-ai/wan-alpha"
    fal_queue_base_url: str = "https://queue.fal.run"
    fal_poll_interval_seconds: float = 5
    fal_max_wait_seconds: int = 900
    video_generation_worker_poll_interval_seconds: int = 5
    video_generation_stream_key: str = "video_generation:stream"
    video_generation_consumer_group: str = "workers"
    video_generation_block_ms: int = 5000
    # provider 최대 실행시간(기본 900s)보다 길게 — 살아있는 긴 job을 회수하지 않도록
    video_generation_reclaim_min_idle_ms: int = 1_200_000
    video_generation_reclaim_count: int = 10
    storage_provider: str = "local"
    local_storage_dir: str = "generated"
    local_public_base_url: str = "/generated"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_region: str = "ap-northeast-2"
    s3_bucket_name: str = ""
    s3_public_base_url: str = ""
    s3_endpoint_url: str = ""
    s3_generated_video_prefix: str = "generated/videos"
    s3_generated_thumbnail_prefix: str = "generated/thumbnails"
    s3_music_prefix: str = "music"
    s3_presigned_url_expire_seconds: int = 900
    tmdb_access_token: str = ""
    tmdb_api_base_url: str = "https://api.themoviedb.org/3"
    tmdb_image_base_url: str = "https://image.tmdb.org/t/p"
    tmdb_poster_size: str = "w500"
    tmdb_language: str = "ko-KR"
    tmdb_timeout_seconds: float = 5


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
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        openai_chat_timeout_seconds=parse_float_env(
            os.getenv("OPENAI_CHAT_TIMEOUT_SECONDS"),
            10.0,
        ),
        openai_chat_max_tokens=parse_int_env(
            os.getenv("OPENAI_CHAT_MAX_TOKENS"),
            250,
        ),
        openai_story_finalize_timeout_seconds=parse_float_env(
            os.getenv("OPENAI_STORY_FINALIZE_TIMEOUT_SECONDS"),
            45.0,
        ),
        openai_story_finalize_max_tokens=parse_int_env(
            os.getenv("OPENAI_STORY_FINALIZE_MAX_TOKENS"),
            900,
        ),
        video_generation_provider=os.getenv("VIDEO_GENERATION_PROVIDER", "auto").strip().lower(),
        generated_media_dir=os.getenv("GENERATED_MEDIA_DIR", "generated"),
        openai_video_model=os.getenv("OPENAI_VIDEO_MODEL", "sora-2"),
        openai_video_size=os.getenv("OPENAI_VIDEO_SIZE", "1280x720"),
        openai_video_seconds=os.getenv("OPENAI_VIDEO_SECONDS", "8"),
        openai_video_poll_interval_seconds=parse_float_env(
            os.getenv("OPENAI_VIDEO_POLL_INTERVAL_SECONDS"),
            5,
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
        video_generation_stream_key=os.getenv(
            "VIDEO_GENERATION_STREAM_KEY",
            "video_generation:stream",
        ),
        video_generation_consumer_group=os.getenv(
            "VIDEO_GENERATION_CONSUMER_GROUP",
            "workers",
        ),
        video_generation_block_ms=parse_int_env(
            os.getenv("VIDEO_GENERATION_BLOCK_MS"),
            5_000,
        ),
        video_generation_reclaim_min_idle_ms=parse_int_env(
            os.getenv("VIDEO_GENERATION_RECLAIM_MIN_IDLE_MS"),
            1_200_000,
        ),
        video_generation_reclaim_count=parse_int_env(
            os.getenv("VIDEO_GENERATION_RECLAIM_COUNT"),
            10,
        ),
        storage_provider=os.getenv("STORAGE_PROVIDER", "local").strip().lower(),
        local_storage_dir=os.getenv("LOCAL_STORAGE_DIR", os.getenv("GENERATED_MEDIA_DIR", "generated")),
        local_public_base_url=os.getenv("LOCAL_PUBLIC_BASE_URL", "/generated").rstrip("/"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", ""),
        aws_region=os.getenv("AWS_REGION", "ap-northeast-2"),
        s3_bucket_name=os.getenv("S3_BUCKET_NAME", ""),
        s3_public_base_url=os.getenv("S3_PUBLIC_BASE_URL", "").rstrip("/"),
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", ""),
        s3_generated_video_prefix=os.getenv("S3_GENERATED_VIDEO_PREFIX", "generated/videos").strip("/"),
        s3_generated_thumbnail_prefix=os.getenv("S3_GENERATED_THUMBNAIL_PREFIX", "generated/thumbnails").strip("/"),
        s3_music_prefix=os.getenv("S3_MUSIC_PREFIX", "music").strip("/"),
        s3_presigned_url_expire_seconds=parse_int_env(
            os.getenv("S3_PRESIGNED_URL_EXPIRE_SECONDS"),
            900,
        ),
        tmdb_access_token=os.getenv("TMDB_ACCESS_TOKEN", ""),
        tmdb_api_base_url=os.getenv("TMDB_API_BASE_URL", "https://api.themoviedb.org/3").rstrip("/"),
        tmdb_image_base_url=os.getenv("TMDB_IMAGE_BASE_URL", "https://image.tmdb.org/t/p").rstrip("/"),
        tmdb_poster_size=os.getenv("TMDB_POSTER_SIZE", "w500").strip("/"),
        tmdb_language=os.getenv("TMDB_LANGUAGE", "ko-KR"),
        tmdb_timeout_seconds=parse_float_env(os.getenv("TMDB_TIMEOUT_SECONDS"), 5),
    )
