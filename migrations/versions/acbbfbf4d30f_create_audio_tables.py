"""create audio tables

Revision ID: acbbfbf4d30f
Revises: 180e37b82ceb
Create Date: 2026-05-15 12:52:03.595421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'acbbfbf4d30f'
down_revision: Union[str, Sequence[str], None] = '180e37b82ceb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table audio_categories
    op.create_table(
        'audio_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table audio_files
    op.create_table(
        'audio_files',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('audio_categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('file_url', sa.String(), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(), nullable=False, server_default='fr'),
        sa.Column('is_local', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('audio_files')
    op.drop_table('audio_categories')