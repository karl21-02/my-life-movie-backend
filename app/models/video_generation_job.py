from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
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


class VideoGenerationJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class VideoGenerationJob(TimestampMixin, Base):
    __tablename__ = "video_generation_jobs"
    __table_args__ = (
        Index("ix_video_generation_jobs_movie_status", "movie_id", "status"),
        Index("ix_video_generation_jobs_user_created_at", "user_id", "created_at"),
        Index("ix_video_generation_jobs_provider_job", "provider", "provider_job_id"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    movie_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[VideoGenerationJobStatus] = mapped_column(
        SQLAlchemyEnum(
            VideoGenerationJobStatus,
            name="video_generation_job_status",
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=VideoGenerationJobStatus.QUEUED,
        server_default=VideoGenerationJobStatus.QUEUED.value,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock", server_default="mock")
    provider_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
