from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0007"
down_revision: str | None = "20260513_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movie_recommendations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="fallback", nullable=False),
        sa.Column("provider_movie_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("poster_url", sa.String(length=1024), server_default="", nullable=False),
        sa.Column("external_url", sa.String(length=1024), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["movie_id"],
            ["movies.id"],
            name="fk_movie_recommendations_movie_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_movie_recommendations"),
    )
    op.create_index(
        "ix_movie_recommendations_movie_rank",
        "movie_recommendations",
        ["movie_id", "rank"],
    )
    op.create_index(
        "ix_movie_recommendations_provider_movie",
        "movie_recommendations",
        ["provider", "provider_movie_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_movie_recommendations_provider_movie", table_name="movie_recommendations")
    op.drop_index("ix_movie_recommendations_movie_rank", table_name="movie_recommendations")
    op.drop_table("movie_recommendations")
