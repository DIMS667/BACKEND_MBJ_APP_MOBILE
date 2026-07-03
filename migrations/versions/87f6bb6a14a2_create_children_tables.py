"""create children tables

Revision ID: 87f6bb6a14a2
Revises: dbb55b5b5abb
Create Date: 2026-05-13 22:43:26.660539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87f6bb6a14a2'
down_revision: Union[str, Sequence[str], None] = 'dbb55b5b5abb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table children
    op.create_table(
        'children',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('parent_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('photo_url', sa.String(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table sensory_profiles
    op.create_table(
        'sensory_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('noise_sensitive', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('light_sensitive', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('color_sensitive', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('motion_sensitive', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )

    # Table child_preferences
    op.create_table(
        'child_preferences',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('child_id', sa.Integer(), sa.ForeignKey('children.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('favorite_activities', sa.JSON(), nullable=True),
        sa.Column('color_theme', sa.String(), nullable=False, server_default='blue'),
        sa.Column('avatar_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('child_preferences')
    op.drop_table('sensory_profiles')
    op.drop_table('children')
