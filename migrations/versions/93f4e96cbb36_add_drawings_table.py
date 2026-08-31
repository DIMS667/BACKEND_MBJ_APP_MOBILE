"""add drawings table

Revision ID: 93f4e96cbb36
Revises: aa98c9c75053
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93f4e96cbb36'
down_revision: Union[str, Sequence[str], None] = 'aa98c9c75053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'drawings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('template_key', sa.String(), nullable=True),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['child_id'], ['children.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_drawings_child_id', 'drawings', ['child_id'])


def downgrade() -> None:
    op.drop_index('ix_drawings_child_id', table_name='drawings')
    op.drop_table('drawings')
