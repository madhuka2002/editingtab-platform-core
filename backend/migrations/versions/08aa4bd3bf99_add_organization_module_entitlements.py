"""add organization module entitlements

Revision ID: 08aa4bd3bf99
Revises: 42d97ba689d9
Create Date: 2026-09-11 21:10:04.241289

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "08aa4bd3bf99"
down_revision: Union[str, Sequence[str], None] = "42d97ba689d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "organization_module_entitlements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("module_code", sa.String(length=50), nullable=False),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "enabled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "disabled_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
        sa.CheckConstraint(
            "module_code = lower(btrim(module_code))",
            name="ck_organization_module_entitlements_code_normalized",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "module_code",
            name="uq_organization_module_entitlements_org_module",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("organization_module_entitlements")
