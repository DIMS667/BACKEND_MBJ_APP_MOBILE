"""Add transition_speed to sensory_profiles.

Revision ID: 047b194702cc
Revises: e4f6a8b0c2d4
Create Date: 2026-08-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "047b194702cc"
down_revision: Union[str, Sequence[str], None] = "e4f6a8b0c2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sensory_profiles",
        sa.Column(
            "transition_speed",
            sa.String(),
            nullable=False,
            server_default="normal",
        ),
    )


def downgrade() -> None:
    op.drop_column("sensory_profiles", "transition_speed")
