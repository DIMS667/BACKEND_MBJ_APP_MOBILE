"""add password reset codes table

Revision ID: 3b616c7d878a
Revises: 93f4e96cbb36
Create Date: 2026-09-01 12:36:40.053942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b616c7d878a'
down_revision: Union[str, Sequence[str], None] = '93f4e96cbb36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_codes',
        sa.Column('code', sa.String(length=6), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_password_reset_codes_id'), 'password_reset_codes', ['id'], unique=False)
    op.create_index(op.f('ix_password_reset_codes_user_id'), 'password_reset_codes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_codes_user_id'), table_name='password_reset_codes')
    op.drop_index(op.f('ix_password_reset_codes_id'), table_name='password_reset_codes')
    op.drop_table('password_reset_codes')
