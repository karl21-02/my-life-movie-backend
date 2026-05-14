from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MovieRecommendation(TimestampMixin, Base):
    __tablename__ = "movie_recommendations"
    __table_args__ = (
        Index("ix_movie_recommendations_movie_rank", "movie_id", "rank"),
        Index("ix_movie_recommendations_provider_movie", "provider", "provider_movie_id"),
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
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="fallback", server_default="fallback")
    provider_movie_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    poster_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="", server_default="")
    external_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
