"""remove difficulty level from stories

Revision ID: aa98c9c75053
Revises: 9516a8513277
Create Date: 2026-08-29 11:25:35.950448

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa98c9c75053'
down_revision: Union[str, Sequence[str], None] = '9516a8513277'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('stories', 'difficulty_level')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'stories',
        sa.Column('difficulty_level', sa.Integer(), server_default='1'),
    )
