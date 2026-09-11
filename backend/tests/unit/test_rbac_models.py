import uuid

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models import (
    OrganizationUser,
    OrganizationUserRole,
    Permission,
    Role,
    RolePermission,
)


def constraint_column_sets(table, constraint_type) -> set[tuple[str, ...]]:
    return {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
    }


def test_role_slug_is_normalized_and_unique_within_organization() -> None:
    organization_a = uuid.uuid4()
    organization_b = uuid.uuid4()
    role_a = Role(
        organization_id=organization_a,
        name="Staff",
        slug=" STAFF ",
    )
    role_b = Role(
        organization_id=organization_b,
        name="Staff",
        slug="staff",
    )

    assert role_a.slug == "staff"
    assert role_b.slug == "staff"
    assert ("organization_id", "slug") in constraint_column_sets(
        Role.__table__,
        UniqueConstraint,
    )
    assert Role.__table__.c.slug.unique is not True


def test_role_has_restrict_organization_fk_and_lookup_constraint() -> None:
    table = Role.__table__

    assert next(iter(table.c.organization_id.foreign_keys)).ondelete == "RESTRICT"
    assert ("organization_id", "slug") in constraint_column_sets(
        table,
        UniqueConstraint,
    )


def test_permission_code_is_required_unique_and_normalized() -> None:
    permission = Permission(code=" MEMBERS.READ ")
    code = Permission.__table__.c.code
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Permission.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert permission.code == "members.read"
    assert code.nullable is False
    assert code.unique is True
    assert code.index is True
    assert checks["ck_permissions_code_normalized"] == (
        "code = lower(btrim(code))"
    )


def test_role_permission_pair_is_composite_primary_key() -> None:
    table = RolePermission.__table__

    assert tuple(table.primary_key.columns.keys()) == (
        "role_id",
        "permission_id",
    )
    assert all(
        foreign_key.ondelete == "RESTRICT"
        for column in (table.c.role_id, table.c.permission_id)
        for foreign_key in column.foreign_keys
    )


def test_membership_role_pair_is_unique_and_tenant_fks_are_composite() -> None:
    table = OrganizationUserRole.__table__
    foreign_key_column_sets = constraint_column_sets(
        table,
        ForeignKeyConstraint,
    )

    assert tuple(table.primary_key.columns.keys()) == (
        "organization_user_id",
        "role_id",
    )
    assert ("organization_id", "organization_user_id") in (
        foreign_key_column_sets
    )
    assert ("organization_id", "role_id") in foreign_key_column_sets
    assert all(
        constraint.ondelete == "RESTRICT"
        for constraint in table.foreign_key_constraints
    )
    assert ("organization_id", "id") in constraint_column_sets(
        OrganizationUser.__table__,
        UniqueConstraint,
    )
