"""add role active state

Revision ID: 6c64c8db15f2
Revises: 08aa4bd3bf99
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6c64c8db15f2"
down_revision: Union[str, Sequence[str], None] = "08aa4bd3bf99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("roles", "is_active")
