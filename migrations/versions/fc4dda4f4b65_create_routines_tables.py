"""create routines tables

Revision ID: fc4dda4f4b65
Revises: 2b8beadff9b8
Create Date: 2026-05-14 07:53:01.043707

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc4dda4f4b65'
down_revision: Union[str, Sequence[str], None] = '2b8beadff9b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table routines
    op.create_table(
        'routines',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('icon_url', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False, server_default='custom'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table routine_steps
    op.create_table(
        'routine_steps',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('routine_id', sa.Integer(), sa.ForeignKey('routines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('audio_url', sa.String(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table routine_sessions
    op.create_table(
        'routine_sessions',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('routine_id', sa.Integer(), sa.ForeignKey('routines.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.String(), nullable=True),
        sa.Column('completed_at', sa.String(), nullable=True),
        sa.Column('steps_completed', sa.Integer(), server_default='0'),
        sa.Column('total_steps', sa.Integer(), server_default='0'),
        sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('routine_sessions')
    op.drop_table('routine_steps')
    op.drop_table('routines')
