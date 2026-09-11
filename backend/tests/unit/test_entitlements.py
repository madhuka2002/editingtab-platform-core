import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.core.modules import BOOKING_MODULE
from app.models import OrganizationModuleEntitlement
from app.services.entitlement import EntitlementService, UnsupportedModuleError


class InMemoryEntitlementRepository:
    def __init__(self) -> None:
        self.entitlements: dict[
            tuple[uuid.UUID, str],
            OrganizationModuleEntitlement,
        ] = {}

    async def find(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> OrganizationModuleEntitlement | None:
        return self.entitlements.get((organization_id, module_code))

    def add(self, entitlement: OrganizationModuleEntitlement) -> None:
        self.entitlements[
            (entitlement.organization_id, entitlement.module_code)
        ] = entitlement


class UnitOfWorkStub:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def run(coroutine):
    return asyncio.run(coroutine)


def make_service():
    repository = InMemoryEntitlementRepository()
    unit_of_work = UnitOfWorkStub()
    return EntitlementService(repository, unit_of_work), repository, unit_of_work


def test_entitlement_schema_normalizes_and_prevents_duplicates() -> None:
    organization_id = uuid.uuid4()
    entitlement = OrganizationModuleEntitlement(
        organization_id=organization_id,
        module_code=" BOOKING ",
    )
    table = OrganizationModuleEntitlement.__table__
    unique_sets = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert entitlement.module_code == BOOKING_MODULE
    assert ("organization_id", "module_code") in unique_sets
    assert checks[
        "ck_organization_module_entitlements_code_normalized"
    ] == "module_code = lower(btrim(module_code))"
    assert next(iter(table.c.organization_id.foreign_keys)).ondelete == "RESTRICT"


def test_booking_can_be_enabled_disabled_and_reactivated() -> None:
    service, repository, unit_of_work = make_service()
    organization_id = uuid.uuid4()

    entitlement = run(service.enable_module(organization_id, " BOOKING "))
    initially_enabled_at = entitlement.enabled_at

    assert run(service.is_enabled(organization_id, BOOKING_MODULE)) is True
    assert len(repository.entitlements) == 1

    disabled = run(service.disable_module(organization_id, BOOKING_MODULE))
    assert disabled is entitlement
    assert entitlement.is_enabled is False
    assert entitlement.disabled_at is not None
    assert run(service.is_enabled(organization_id, BOOKING_MODULE)) is False

    reactivated = run(service.enable_module(organization_id, BOOKING_MODULE))
    assert reactivated is entitlement
    assert entitlement.is_enabled is True
    assert entitlement.disabled_at is None
    assert entitlement.enabled_at >= initially_enabled_at
    assert len(repository.entitlements) == 1
    assert unit_of_work.commits == 3


def test_enabling_enabled_booking_is_idempotent() -> None:
    service, repository, _ = make_service()
    organization_id = uuid.uuid4()

    first = run(service.enable_module(organization_id, BOOKING_MODULE))
    second = run(service.enable_module(organization_id, BOOKING_MODULE))

    assert first is second
    assert len(repository.entitlements) == 1


def test_unsupported_module_is_rejected() -> None:
    service, _, unit_of_work = make_service()

    with pytest.raises(UnsupportedModuleError):
        run(service.enable_module(uuid.uuid4(), "social"))
    assert unit_of_work.rollbacks == 1
