"""create communication tables

Revision ID: 65749b0b0b7a
Revises: 87f6bb6a14a2
Create Date: 2026-05-14 00:44:01.780365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65749b0b0b7a'
down_revision: Union[str, Sequence[str], None] = '87f6bb6a14a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table picto_categories
    op.create_table(
        'picto_categories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=False, server_default='#4A90D9'),
        sa.Column('order', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table pictograms
    op.create_table(
        'pictograms',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('category_id', sa.Integer(), sa.ForeignKey('picto_categories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table favorite_pictos
    op.create_table(
        'favorite_pictos',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('picto_id', sa.Integer(), sa.ForeignKey('pictograms.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table sentence_histories
    op.create_table(
        'sentence_histories',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sentence_pictos', sa.JSON(), nullable=True),
        sa.Column('sentence_text', sa.String(), nullable=False),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('sentence_histories')
    op.drop_table('favorite_pictos')
    op.drop_table('pictograms')
    op.drop_table('picto_categories')
