"""persist retryable private-file deletion jobs

Revision ID: e91f62a7b830
Revises: c5d83e11f742
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e91f62a7b830"
down_revision: Union[str, Sequence[str], None] = "c5d83e11f742"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pending_file_deletions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("owner_directory", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "pictogram_media",
        sa.Column("child_id", sa.Integer(), sa.ForeignKey("children.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_pictogram_media_child_id", "pictogram_media", ["child_id"])
    op.add_column(
        "story_media",
        sa.Column("child_id", sa.Integer(), sa.ForeignKey("children.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_story_media_child_id", "story_media", ["child_id"])


def downgrade() -> None:
    op.drop_index("ix_story_media_child_id", table_name="story_media")
    op.drop_column("story_media", "child_id")
    op.drop_index("ix_pictogram_media_child_id", table_name="pictogram_media")
    op.drop_column("pictogram_media", "child_id")
    op.drop_table("pending_file_deletions")
