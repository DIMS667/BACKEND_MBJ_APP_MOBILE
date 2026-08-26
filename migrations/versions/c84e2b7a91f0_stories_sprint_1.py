"""stories sprint 1

Revision ID: c84e2b7a91f0
Revises: 7d1c9a4e8b20
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c84e2b7a91f0"
down_revision: Union[str, Sequence[str], None] = "7d1c9a4e8b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "stories",
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("stories", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.add_column("stories", sa.Column("child_id", sa.Integer(), nullable=True))
    op.add_column("stories", sa.Column("client_uuid", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_stories_owner_id",
        "stories",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_stories_child_id",
        "stories",
        "children",
        ["child_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_stories_owner_id", "stories", ["owner_id"])
    op.create_index("ix_stories_child_id", "stories", ["child_id"])
    op.create_index(
        "ix_stories_client_uuid",
        "stories",
        ["client_uuid"],
        unique=True,
    )

    op.add_column(
        "story_pages",
        sa.Column("pictogram_url", sa.String(), nullable=True),
    )
    op.add_column(
        "story_pages",
        sa.Column("local_page_key", sa.String(64), nullable=True),
    )
    op.add_column(
        "story_pages",
        sa.Column("next_page_number", sa.Integer(), nullable=True),
    )

    op.create_table(
        "story_choices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "page_id",
            sa.Integer(),
            sa.ForeignKey("story_pages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("pictogram_url", sa.String(), nullable=True),
        sa.Column("next_page_number", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_story_choices_page_id", "story_choices", ["page_id"])

    op.execute(
        """
        DELETE FROM story_progress older
        USING story_progress newer
        WHERE older.story_id = newer.story_id
          AND older.child_id = newer.child_id
          AND older.id < newer.id
        """
    )
    op.add_column(
        "story_progress",
        sa.Column(
            "selected_choices",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_unique_constraint(
        "uq_story_progress_child",
        "story_progress",
        ["story_id", "child_id"],
    )

    op.create_table(
        "story_favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "story_id",
            sa.Integer(),
            sa.ForeignKey("stories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            sa.Integer(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=False,
        ),
        *_timestamps(),
        sa.UniqueConstraint(
            "story_id",
            "child_id",
            name="uq_story_favorite_child",
        ),
    )

    op.create_table(
        "story_media",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_uuid", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_story_media_owner_id", "story_media", ["owner_id"])
    op.create_index(
        "ix_story_media_client_uuid",
        "story_media",
        ["client_uuid"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_story_media_owner_client",
        "story_media",
        ["owner_id", "client_uuid"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_story_media_owner_client",
        "story_media",
        type_="unique",
    )
    op.drop_index("ix_story_media_client_uuid", table_name="story_media")
    op.drop_index("ix_story_media_owner_id", table_name="story_media")
    op.drop_table("story_media")
    op.drop_table("story_favorites")

    op.drop_constraint(
        "uq_story_progress_child",
        "story_progress",
        type_="unique",
    )
    op.drop_column("story_progress", "selected_choices")

    op.drop_index("ix_story_choices_page_id", table_name="story_choices")
    op.drop_table("story_choices")
    op.drop_column("story_pages", "next_page_number")
    op.drop_column("story_pages", "local_page_key")
    op.drop_column("story_pages", "pictogram_url")

    op.drop_index("ix_stories_client_uuid", table_name="stories")
    op.drop_index("ix_stories_child_id", table_name="stories")
    op.drop_index("ix_stories_owner_id", table_name="stories")
    op.drop_constraint("fk_stories_child_id", "stories", type_="foreignkey")
    op.drop_constraint("fk_stories_owner_id", "stories", type_="foreignkey")
    op.drop_column("stories", "client_uuid")
    op.drop_column("stories", "child_id")
    op.drop_column("stories", "owner_id")
    op.drop_column("stories", "is_custom")
