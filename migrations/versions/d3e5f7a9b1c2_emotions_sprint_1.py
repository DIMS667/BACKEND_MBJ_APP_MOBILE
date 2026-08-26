"""Add offline-safe emotion records and calming feedback.

Revision ID: d3e5f7a9b1c2
Revises: f2a6c1d4e9b7
Create Date: 2026-08-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e5f7a9b1c2"
down_revision: Union[str, Sequence[str], None] = "f2a6c1d4e9b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "emotion_records",
        sa.Column("client_uuid", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "emotion_records",
        sa.Column("context_key", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "emotion_records",
        sa.Column("intensity", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "emotion_records",
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    op.execute(
        sa.text(
            "UPDATE emotion_records "
            "SET client_uuid = 'legacy-emotion-' || CAST(id AS VARCHAR) "
            "WHERE client_uuid IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE emotion_records "
            "SET recorded_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
        )
    )
    op.execute(
        sa.text(
            "UPDATE emotion_records SET intensity = CASE "
            "WHEN LOWER(context) LIKE '%intensité:doux%' "
            "  OR LOWER(context) LIKE '%intensite:doux%' "
            "  OR LOWER(context) LIKE '%intensité:faible%' "
            "  OR LOWER(context) LIKE '%intensite:faible%' THEN 'doux' "
            "WHEN LOWER(context) LIKE '%intensité:moyen%' "
            "  OR LOWER(context) LIKE '%intensite:moyen%' THEN 'moyen' "
            "WHEN LOWER(context) LIKE '%intensité:fort%' "
            "  OR LOWER(context) LIKE '%intensite:fort%' THEN 'fort' "
            "ELSE NULL END "
            "WHERE context IS NOT NULL"
        )
    )

    context_mappings = {
        "maison": "maison",
        "école": "ecole",
        "ecole": "ecole",
        "repas": "repas",
        "transport": "transport",
        "bruit": "bruit",
        "soin": "soin",
        "jeu": "jeu",
        "changement": "changement",
        "attente": "attente",
        "avec_autres": "avec_autres",
        "seul": "seul",
        "autre": "autre",
    }
    for legacy_value, context_key in context_mappings.items():
        op.execute(
            sa.text(
                "UPDATE emotion_records SET context_key = :context_key "
                "WHERE context_key IS NULL "
                "AND (LOWER(context) = :legacy_value "
                "OR LOWER(context) LIKE :legacy_prefix)"
            ).bindparams(
                context_key=context_key,
                legacy_value=legacy_value,
                legacy_prefix=f"{legacy_value}|%",
            )
        )

    op.alter_column(
        "emotion_records",
        "client_uuid",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "emotion_records",
        "recorded_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        existing_server_default=sa.func.now(),
    )
    op.create_unique_constraint(
        "uq_emotion_records_child_client",
        "emotion_records",
        ["child_id", "client_uuid"],
    )
    op.create_check_constraint(
        "ck_emotion_records_intensity",
        "emotion_records",
        "intensity IS NULL OR intensity IN ('doux', 'moyen', 'fort')",
    )
    op.create_index(
        "ix_emotion_records_child_recorded_at",
        "emotion_records",
        ["child_id", "recorded_at"],
    )

    op.add_column(
        "calming_activities",
        sa.Column(
            "display_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "calming_activities",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE calming_activities SET display_order = CASE type "
            "WHEN 'breathing' THEN 1 "
            "WHEN 'music' THEN 2 "
            "WHEN 'animation' THEN 3 "
            "WHEN 'game' THEN 4 "
            "ELSE 100 + id END"
        )
    )

    op.create_table(
        "calming_activity_feedback",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "child_id",
            sa.Integer(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "emotion_record_id",
            sa.Integer(),
            sa.ForeignKey("emotion_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            sa.Integer(),
            sa.ForeignKey("calming_activities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("client_uuid", sa.String(length=64), nullable=False),
        sa.Column("helped", sa.Boolean(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "child_id",
            "client_uuid",
            name="uq_calming_feedback_child_client",
        ),
    )
    op.create_index(
        "ix_calming_feedback_child_activity_recorded",
        "calming_activity_feedback",
        ["child_id", "activity_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_calming_feedback_child_activity_recorded",
        table_name="calming_activity_feedback",
    )
    op.drop_table("calming_activity_feedback")

    op.drop_column("calming_activities", "is_active")
    op.drop_column("calming_activities", "display_order")

    op.drop_index(
        "ix_emotion_records_child_recorded_at",
        table_name="emotion_records",
    )
    op.drop_constraint(
        "ck_emotion_records_intensity",
        "emotion_records",
        type_="check",
    )
    op.drop_constraint(
        "uq_emotion_records_child_client",
        "emotion_records",
        type_="unique",
    )
    op.drop_column("emotion_records", "recorded_at")
    op.drop_column("emotion_records", "intensity")
    op.drop_column("emotion_records", "context_key")
    op.drop_column("emotion_records", "client_uuid")
