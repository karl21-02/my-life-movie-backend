import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_name: str = "My Life Movie API"
    service_name: str = "my-life-movie-backend"
    environment: str = "local"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "local"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
