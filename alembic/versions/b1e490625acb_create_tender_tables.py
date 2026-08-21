"""create tender tables

Revision ID: b1e490625acb
Revises: 
Create Date: 2026-08-21 13:59:57.753612

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


tender_status = postgresql.ENUM(
    "draft",
    "active",
    "won",
    "lost",
    name="tender_status",
    create_type=False,
)


revision: str = "b1e490625acb"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    tender_status.create(op.get_bind(), checkfirst=False)
    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            tender_status,
            server_default="draft",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "tender_status_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        sa.Column("old_status", tender_status, nullable=False),
        sa.Column("new_status", tender_status, nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tender_status_history_tender_id"),
        "tender_status_history",
        ["tender_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_tender_status_history_tender_id"),
        table_name="tender_status_history",
    )
    op.drop_table("tender_status_history")
    op.drop_table("tenders")
    tender_status.drop(op.get_bind(), checkfirst=False)
