from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260513_0004"
down_revision: str | None = "20260509_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movies", sa.Column("story_brief", sa.JSON(), nullable=True))
    op.add_column("movies", sa.Column("scene_plan", sa.JSON(), nullable=True))
    op.add_column("movies", sa.Column("generation_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("movies", "generation_prompt")
    op.drop_column("movies", "scene_plan")
    op.drop_column("movies", "story_brief")
