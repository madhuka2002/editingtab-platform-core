import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrganizationUserRole(Base):
    __tablename__ = "organization_user_roles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "organization_user_id"],
            [
                "organization_users.organization_id",
                "organization_users.id",
            ],
            name="fk_organization_user_roles_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_organization_user_roles_role",
            ondelete="RESTRICT",
        ),
        Index("ix_organization_user_roles_role_id", "role_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    organization_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
