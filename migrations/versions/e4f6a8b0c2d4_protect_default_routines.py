"""Protect default routines and support idempotent custom steps.

Revision ID: e4f6a8b0c2d4
Revises: d3e5f7a9b1c2
Create Date: 2026-08-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f6a8b0c2d4"
down_revision: Union[str, Sequence[str], None] = "d3e5f7a9b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "routines",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE routines SET is_default = true "
            "WHERE type <> 'custom'"
        )
    )

    op.add_column(
        "routine_steps",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "routine_steps",
        sa.Column("client_uuid", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE routine_steps SET is_default = true "
            "WHERE routine_id IN ("
            "SELECT id FROM routines WHERE is_default = true"
            ")"
        )
    )

    op.create_index(
        "ix_routine_steps_client_uuid",
        "routine_steps",
        ["client_uuid"],
    )
    op.create_unique_constraint(
        "uq_routine_steps_routine_client",
        "routine_steps",
        ["routine_id", "client_uuid"],
    )
    # Réparer les ordres historiques avant d'activer les contraintes. Les
    # ordres positifs existants restent prioritaires, puis les égalités et les
    # valeurs invalides sont départagées de façon stable par l'identifiant.
    op.execute(
        sa.text(
            'WITH ranked_steps AS ('
            'SELECT id, ROW_NUMBER() OVER ('
            'PARTITION BY routine_id '
            'ORDER BY CASE WHEN "order" >= 1 THEN 0 ELSE 1 END, '
            'CASE WHEN "order" >= 1 THEN "order" ELSE NULL END, id'
            ') AS normalized_order '
            'FROM routine_steps'
            ') '
            'UPDATE routine_steps AS step '
            'SET "order" = ranked_steps.normalized_order '
            'FROM ranked_steps '
            'WHERE step.id = ranked_steps.id '
            'AND step."order" IS DISTINCT FROM ranked_steps.normalized_order'
        )
    )
    op.create_unique_constraint(
        "uq_routine_steps_routine_order",
        "routine_steps",
        ["routine_id", "order"],
    )
    op.create_check_constraint(
        "ck_routine_steps_order_positive",
        "routine_steps",
        '"order" >= 1',
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_routine_steps_order_positive",
        "routine_steps",
        type_="check",
    )
    op.drop_constraint(
        "uq_routine_steps_routine_order",
        "routine_steps",
        type_="unique",
    )
    op.drop_constraint(
        "uq_routine_steps_routine_client",
        "routine_steps",
        type_="unique",
    )
    op.drop_index(
        "ix_routine_steps_client_uuid",
        table_name="routine_steps",
    )
    op.drop_column("routine_steps", "client_uuid")
    op.drop_column("routine_steps", "is_default")
    op.drop_column("routines", "is_default")
