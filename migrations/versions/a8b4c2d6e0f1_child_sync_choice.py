"""Keep child-data synchronization off until the parent chooses it.

Revision ID: a8b4c2d6e0f1
Revises: e91f62a7b830
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b4c2d6e0f1"
down_revision: Union[str, Sequence[str], None] = "e91f62a7b830"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("child_sync_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("child_sync_choice_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "child_sync_choice_at")
    op.drop_column("users", "child_sync_enabled")
