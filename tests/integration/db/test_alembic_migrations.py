import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


pytestmark = pytest.mark.integration


def test_alembic_upgrade_head_creates_auth_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic-test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()

    try:
        command.upgrade(Config("alembic.ini"), "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)

        assert inspector.has_table("users")
        assert inspector.has_table("auth_refresh_tokens")
        assert inspector.has_table("movies")
        assert inspector.has_table("video_generation_jobs")
        assert {column["name"] for column in inspector.get_columns("auth_refresh_tokens")} >= {
            "id",
            "user_id",
            "token_hash",
            "token_family_id",
            "status",
            "expires_at",
        }
        assert {column["name"] for column in inspector.get_columns("movies")} >= {
            "id",
            "user_id",
            "theme_id",
            "status",
            "story_brief",
            "scene_plan",
            "generation_prompt",
        }
        assert {column["name"] for column in inspector.get_columns("video_generation_jobs")} >= {
            "id",
            "movie_id",
            "user_id",
            "status",
            "provider",
            "progress",
            "input_snapshot",
            "output_url",
            "thumbnail_url",
            "error_code",
            "error_message",
        }

        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version"),
            ).scalar_one()

        assert version == "20260513_0006"
        engine.dispose()
    finally:
        get_settings.cache_clear()
