"""add account deletion codes table

Revision ID: fabde132271c
Revises: 3b616c7d878a
Create Date: 2026-09-03 20:47:11.740528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fabde132271c'
down_revision: Union[str, Sequence[str], None] = '3b616c7d878a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'account_deletion_codes',
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
    op.create_index(op.f('ix_account_deletion_codes_id'), 'account_deletion_codes', ['id'], unique=False)
    op.create_index(op.f('ix_account_deletion_codes_user_id'), 'account_deletion_codes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_account_deletion_codes_user_id'), table_name='account_deletion_codes')
    op.drop_index(op.f('ix_account_deletion_codes_id'), table_name='account_deletion_codes')
    op.drop_table('account_deletion_codes')
