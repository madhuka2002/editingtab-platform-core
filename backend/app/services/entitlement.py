import uuid
from datetime import UTC, datetime

from app.core.modules import SUPPORTED_MODULE_CODES
from app.models import OrganizationModuleEntitlement
from app.repositories import EntitlementRepository, UnitOfWork


class UnsupportedModuleError(ValueError):
    pass


class EntitlementService:
    def __init__(
        self,
        repository: EntitlementRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    async def enable_module(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> OrganizationModuleEntitlement:
        try:
            entitlement = await self.ensure_enabled(
                organization_id,
                module_code,
            )
            await self._unit_of_work.commit()
            return entitlement
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def ensure_enabled(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> OrganizationModuleEntitlement:
        normalized_code = self._normalize_supported_code(module_code)
        entitlement = await self._repository.find(
            organization_id,
            normalized_code,
        )
        now = datetime.now(UTC)

        if entitlement is None:
            entitlement = OrganizationModuleEntitlement(
                id=uuid.uuid4(),
                organization_id=organization_id,
                module_code=normalized_code,
                is_enabled=True,
                enabled_at=now,
            )
            self._repository.add(entitlement)
        elif not entitlement.is_enabled:
            entitlement.is_enabled = True
            entitlement.enabled_at = now
            entitlement.disabled_at = None

        return entitlement

    async def disable_module(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> OrganizationModuleEntitlement | None:
        try:
            normalized_code = self._normalize_supported_code(module_code)
            entitlement = await self._repository.find(
                organization_id,
                normalized_code,
            )
            if entitlement is not None and entitlement.is_enabled:
                entitlement.is_enabled = False
                entitlement.disabled_at = datetime.now(UTC)
            await self._unit_of_work.commit()
            return entitlement
        except Exception:
            await self._unit_of_work.rollback()
            raise

    async def is_enabled(
        self,
        organization_id: uuid.UUID,
        module_code: str,
    ) -> bool:
        normalized_code = self._normalize_supported_code(module_code)
        entitlement = await self._repository.find(
            organization_id,
            normalized_code,
        )
        return entitlement is not None and entitlement.is_enabled

    @staticmethod
    def _normalize_supported_code(module_code: str) -> str:
        normalized_code = module_code.strip().lower()
        if normalized_code not in SUPPORTED_MODULE_CODES:
            raise UnsupportedModuleError("Unsupported module")
        return normalized_code
