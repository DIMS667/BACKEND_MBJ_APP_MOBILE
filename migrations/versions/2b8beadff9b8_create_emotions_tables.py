"""create emotions tables

Revision ID: 2b8beadff9b8
Revises: 65749b0b0b7a
Create Date: 2026-05-14 02:33:52.373483

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b8beadff9b8'
down_revision: Union[str, Sequence[str], None] = '65749b0b0b7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table emotions
    op.create_table(
        'emotions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('color', sa.String(), nullable=False, server_default='#4A90D9'),
        sa.Column('is_positive', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table emotion_records
    op.create_table(
        'emotion_records',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('emotion_id', sa.Integer(), sa.ForeignKey('emotions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('context', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table calming_activities
    op.create_table(
        'calming_activities',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('content_url', sa.String(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), server_default='60'),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('calming_activities')
    op.drop_table('emotion_records')
    op.drop_table('emotions')