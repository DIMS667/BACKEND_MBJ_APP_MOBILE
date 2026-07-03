"""create stories tables

Revision ID: 180e37b82ceb
Revises: a05bed9cffbe
Create Date: 2026-05-15 12:05:26.581596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '180e37b82ceb'
down_revision: Union[str, Sequence[str], None] = 'a05bed9cffbe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table stories
    op.create_table(
        'stories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('cover_url', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('difficulty_level', sa.Integer(), server_default='1'),
        sa.Column('is_offline_available', sa.Boolean(), server_default=sa.true()),
        sa.Column('total_pages', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table story_pages
    op.create_table(
        'story_pages',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('story_id', sa.Integer(), sa.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('animation_type', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table story_progress
    op.create_table(
        'story_progress',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('story_id', sa.Integer(), sa.ForeignKey('stories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('last_page', sa.Integer(), server_default='1'),
        sa.Column('is_completed', sa.Boolean(), server_default=sa.false()),
        sa.Column('read_count', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('story_progress')
    op.drop_table('story_pages')
    op.drop_table('stories')