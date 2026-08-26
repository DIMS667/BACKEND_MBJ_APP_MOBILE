"""add game mastery metrics

Revision ID: 7d1c9a4e8b20
Revises: acbbfbf4d30f
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d1c9a4e8b20"
down_revision: Union[str, Sequence[str], None] = "acbbfbf4d30f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("game_scores", sa.Column("session_id", sa.String(64), nullable=True))
    op.add_column(
        "game_scores",
        sa.Column("correct_answers", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_scores",
        sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_scores",
        sa.Column("mistake_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_scores",
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_scores",
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "game_scores",
        sa.Column(
            "independent_success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "game_scores",
        sa.Column("evidence_score", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint(
        "uq_game_scores_session",
        "game_scores",
        ["game_id", "child_id", "session_id"],
    )

    op.add_column(
        "game_progress",
        sa.Column("mastery_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_progress",
        sa.Column("independent_streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_progress",
        sa.Column("struggle_streak", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "game_progress",
        sa.Column("is_mastered", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("game_progress", "is_mastered")
    op.drop_column("game_progress", "struggle_streak")
    op.drop_column("game_progress", "independent_streak")
    op.drop_column("game_progress", "mastery_percent")

    op.drop_constraint("uq_game_scores_session", "game_scores", type_="unique")
    op.drop_column("game_scores", "evidence_score")
    op.drop_column("game_scores", "independent_success")
    op.drop_column("game_scores", "completed")
    op.drop_column("game_scores", "hints_used")
    op.drop_column("game_scores", "mistake_count")
    op.drop_column("game_scores", "total_questions")
    op.drop_column("game_scores", "correct_answers")
    op.drop_column("game_scores", "session_id")
