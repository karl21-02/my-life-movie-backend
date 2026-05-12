from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0003"
down_revision: str | None = "20260507_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("theme_id", sa.Integer(), nullable=False),
        sa.Column("music_id", sa.Integer(), nullable=True),
        sa.Column("current_draft", sa.Text(), nullable=True),
        sa.Column("files", sa.JSON(), nullable=True),
        sa.Column("chat_history", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="DRAFT", nullable=False),
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
            ["user_id"],
            ["users.id"],
            name="fk_movies_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_movies"),
    )
    op.create_index("ix_movies_user_status", "movies", ["user_id", "status"])
    op.create_index("ix_movies_created_at", "movies", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_movies_created_at", table_name="movies")
    op.drop_index("ix_movies_user_status", table_name="movies")
    op.drop_table("movies")
