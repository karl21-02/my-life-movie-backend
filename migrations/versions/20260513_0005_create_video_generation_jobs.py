from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0005"
down_revision: str | None = "20260513_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_generation_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("movie_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column("provider", sa.String(length=64), server_default="mock", nullable=False),
        sa.Column("provider_job_id", sa.String(length=255), nullable=True),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("output_url", sa.String(length=1024), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=1024), nullable=True),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            name="fk_video_generation_jobs_movie_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_video_generation_jobs_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_video_generation_jobs"),
    )
    op.create_index(
        "ix_video_generation_jobs_movie_status",
        "video_generation_jobs",
        ["movie_id", "status"],
    )
    op.create_index(
        "ix_video_generation_jobs_user_created_at",
        "video_generation_jobs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_video_generation_jobs_provider_job",
        "video_generation_jobs",
        ["provider", "provider_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_video_generation_jobs_provider_job", table_name="video_generation_jobs")
    op.drop_index("ix_video_generation_jobs_user_created_at", table_name="video_generation_jobs")
    op.drop_index("ix_video_generation_jobs_movie_status", table_name="video_generation_jobs")
    op.drop_table("video_generation_jobs")
