from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models import OrganizationUser, RefreshToken, User


def test_user_email_is_normalized() -> None:
    user = User(
        email="  USER@Example.COM  ",
        password_hash="not-a-plaintext-password",
    )

    assert user.email == "user@example.com"


def test_user_email_is_unique_and_indexed() -> None:
    email = User.__table__.c.email

    assert email.nullable is False
    assert email.unique is True
    assert email.index is True


def test_user_email_has_database_normalization_constraint() -> None:
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in User.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert constraints["ck_users_email_normalized"] == (
        "email = lower(btrim(email))"
    )


def test_organization_membership_pair_is_unique() -> None:
    table = OrganizationUser.__table__
    unique_column_sets = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("organization_id", "user_id") in unique_column_sets


def test_organization_membership_has_user_lookup_index_only() -> None:
    index_column_sets = {
        tuple(index.columns.keys())
        for index in OrganizationUser.__table__.indexes
    }

    assert ("user_id",) in index_column_sets
    assert ("organization_id",) not in index_column_sets


def test_organization_membership_foreign_keys_restrict_deletion() -> None:
    table = OrganizationUser.__table__

    assert next(iter(table.c.organization_id.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "RESTRICT"


def test_refresh_token_persistence_is_digest_only_and_restricts_deletion() -> None:
    table = RefreshToken.__table__

    assert "token_digest" in table.c
    assert "refresh_token" not in table.c
    assert table.c.token_digest.unique is True
    assert table.c.token_digest.index is True
    assert next(iter(table.c.user_id.foreign_keys)).ondelete == "RESTRICT"
