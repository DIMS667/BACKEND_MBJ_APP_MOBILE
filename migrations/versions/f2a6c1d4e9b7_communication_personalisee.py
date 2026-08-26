"""communication personnalisée

Revision ID: f2a6c1d4e9b7
Revises: c84e2b7a91f0
Create Date: 2026-07-31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6c1d4e9b7"
down_revision: Union[str, Sequence[str], None] = "c84e2b7a91f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE picto_categories "
        "DROP CONSTRAINT IF EXISTS picto_categories_name_key"
    )
    op.add_column(
        "picto_categories",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "picto_categories",
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "picto_categories",
        sa.Column(
            "child_id",
            sa.Integer(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "picto_categories",
        sa.Column("client_uuid", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_picto_categories_owner_id",
        "picto_categories",
        ["owner_id"],
    )
    op.create_index(
        "ix_picto_categories_child_id",
        "picto_categories",
        ["child_id"],
    )
    op.create_index(
        "ix_picto_categories_client_uuid",
        "picto_categories",
        ["client_uuid"],
    )
    op.create_unique_constraint(
        "uq_picto_categories_owner_client",
        "picto_categories",
        ["owner_id", "client_uuid"],
    )

    op.add_column(
        "pictograms",
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "pictograms",
        sa.Column(
            "child_id",
            sa.Integer(),
            sa.ForeignKey("children.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "pictograms",
        sa.Column("client_uuid", sa.String(length=64), nullable=True),
    )
    op.alter_column(
        "pictograms",
        "is_default",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.true(),
    )
    op.create_index("ix_pictograms_owner_id", "pictograms", ["owner_id"])
    op.create_index("ix_pictograms_child_id", "pictograms", ["child_id"])
    op.create_index(
        "ix_pictograms_client_uuid",
        "pictograms",
        ["client_uuid"],
    )
    op.create_unique_constraint(
        "uq_pictograms_owner_client",
        "pictograms",
        ["owner_id", "client_uuid"],
    )

    op.create_table(
        "pictogram_media",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("client_uuid", sa.String(length=64), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "owner_id",
            "client_uuid",
            name="uq_pictogram_media_owner_client",
        ),
    )
    op.create_index(
        "ix_pictogram_media_owner_id",
        "pictogram_media",
        ["owner_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    custom_count = connection.execute(
        sa.text(
            "SELECT "
            "(SELECT COUNT(*) FROM picto_categories "
            " WHERE is_default = false) + "
            "(SELECT COUNT(*) FROM pictograms WHERE is_default = false)"
        )
    ).scalar_one()
    if custom_count:
        raise RuntimeError(
            "Downgrade refused: export or remove custom pictograms first."
        )

    op.drop_index(
        "ix_pictogram_media_owner_id",
        table_name="pictogram_media",
    )
    op.drop_table("pictogram_media")

    op.drop_constraint(
        "uq_pictograms_owner_client",
        "pictograms",
        type_="unique",
    )
    op.drop_index("ix_pictograms_client_uuid", table_name="pictograms")
    op.drop_index("ix_pictograms_child_id", table_name="pictograms")
    op.drop_index("ix_pictograms_owner_id", table_name="pictograms")
    op.drop_column("pictograms", "client_uuid")
    op.drop_column("pictograms", "child_id")
    op.drop_column("pictograms", "owner_id")
    op.alter_column(
        "pictograms",
        "is_default",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.true(),
    )

    op.drop_constraint(
        "uq_picto_categories_owner_client",
        "picto_categories",
        type_="unique",
    )
    op.drop_index(
        "ix_picto_categories_client_uuid",
        table_name="picto_categories",
    )
    op.drop_index(
        "ix_picto_categories_child_id",
        table_name="picto_categories",
    )
    op.drop_index(
        "ix_picto_categories_owner_id",
        table_name="picto_categories",
    )
    op.drop_column("picto_categories", "client_uuid")
    op.drop_column("picto_categories", "child_id")
    op.drop_column("picto_categories", "owner_id")
    op.drop_column("picto_categories", "is_default")
    op.create_unique_constraint(
        "picto_categories_name_key",
        "picto_categories",
        ["name"],
    )
