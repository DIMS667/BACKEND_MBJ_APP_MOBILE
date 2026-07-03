"""create games tables

Revision ID: a05bed9cffbe
Revises: fc4dda4f4b65
Create Date: 2026-05-14 18:42:37.071828

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a05bed9cffbe'
down_revision: Union[str, Sequence[str], None] = 'fc4dda4f4b65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table game_categories
    op.create_table(
        'game_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=False, server_default='#4A90D9'),
        sa.Column('order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table games
    op.create_table(
        'games',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('game_categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('min_level', sa.Integer(), server_default='1'),
        sa.Column('max_level', sa.Integer(), server_default='5'),
        sa.Column('is_offline_available', sa.Boolean(), server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table game_scores
    op.create_table(
        'game_scores',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table game_progress
    op.create_table(
        'game_progress',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('game_id', sa.Integer(), sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_level', sa.Integer(), server_default='1'),
        sa.Column('best_score', sa.Integer(), server_default='0'),
        sa.Column('total_plays', sa.Integer(), server_default='0'),
        sa.Column('consecutive_successes', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('game_progress')
    op.drop_table('game_scores')
    op.drop_table('games')
    op.drop_table('game_categories')
