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


def parse_csv_env(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default

    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "local"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=parse_csv_env(
            os.getenv("CORS_ORIGINS"),
            ["http://localhost:3000", "http://127.0.0.1:3000"],
        ),
        database_url=os.getenv("DATABASE_URL"),
    )
