"""Add missing indexes on FK/filter columns and harden GameProgress uniqueness.

Revision ID: 9516a8513277
Revises: 047b194702cc
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9516a8513277"
down_revision: Union[str, Sequence[str], None] = "047b194702cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_children_parent_id", "children", ["parent_id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_routines_child_id", "routines", ["child_id"])
    op.create_index("ix_routine_sessions_routine_id", "routine_sessions", ["routine_id"])
    op.create_index("ix_story_pages_story_id", "story_pages", ["story_id"])
    op.create_index("ix_games_category_id", "games", ["category_id"])
    op.create_index("ix_audio_files_category_id", "audio_files", ["category_id"])
    op.create_index(
        "ix_game_scores_child_created", "game_scores", ["child_id", "created_at"]
    )

    # game_progress : dédupliquer les éventuels doublons (child_id, game_id)
    # avant de poser la contrainte unique — on garde la ligne la plus
    # avancée (best_score le plus haut, puis id le plus récent en cas d'égalité).
    op.execute(
        sa.text(
            "DELETE FROM game_progress a USING game_progress b "
            "WHERE a.child_id = b.child_id AND a.game_id = b.game_id "
            "AND (a.best_score, a.id) < (b.best_score, b.id)"
        )
    )
    op.create_unique_constraint(
        "uq_game_progress_child_game", "game_progress", ["child_id", "game_id"]
    )

    # story_progress / story_favorites : la contrainte unique existante
    # (story_id, child_id) est remplacée par (child_id, story_id) — même
    # garantie d'unicité, mais l'index qui la porte sert enfin les requêtes
    # qui filtrent par enfant seul (tableau de bord, listes de progression).
    op.drop_constraint("uq_story_progress_child", "story_progress", type_="unique")
    op.create_unique_constraint(
        "uq_story_progress_child_story", "story_progress", ["child_id", "story_id"]
    )
    op.drop_constraint("uq_story_favorite_child", "story_favorites", type_="unique")
    op.create_unique_constraint(
        "uq_story_favorite_child_story", "story_favorites", ["child_id", "story_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_story_favorite_child_story", "story_favorites", type_="unique"
    )
    op.create_unique_constraint(
        "uq_story_favorite_child", "story_favorites", ["story_id", "child_id"]
    )
    op.drop_constraint(
        "uq_story_progress_child_story", "story_progress", type_="unique"
    )
    op.create_unique_constraint(
        "uq_story_progress_child", "story_progress", ["story_id", "child_id"]
    )

    op.drop_constraint("uq_game_progress_child_game", "game_progress", type_="unique")

    op.drop_index("ix_game_scores_child_created", table_name="game_scores")
    op.drop_index("ix_audio_files_category_id", table_name="audio_files")
    op.drop_index("ix_games_category_id", table_name="games")
    op.drop_index("ix_story_pages_story_id", table_name="story_pages")
    op.drop_index("ix_routine_sessions_routine_id", table_name="routine_sessions")
    op.drop_index("ix_routines_child_id", table_name="routines")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_children_parent_id", table_name="children")
