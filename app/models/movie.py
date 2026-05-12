from enum import Enum

from sqlalchemy import (
    BigInteger,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MovieStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Movie(TimestampMixin, Base):
    __tablename__ = "movies"
    __table_args__ = (
        Index("ix_movies_user_status", "user_id", "status"),
        Index("ix_movies_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    theme_id: Mapped[int] = mapped_column(Integer, nullable=False)
    music_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scene_plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generation_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    chat_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[MovieStatus] = mapped_column(
        SQLAlchemyEnum(MovieStatus, name="movie_status", native_enum=False, length=32),
        nullable=False,
        default=MovieStatus.DRAFT,
        server_default=MovieStatus.DRAFT.value,
    )
