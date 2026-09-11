import uuid

from app.models import OrganizationUser, OrganizationUserRole, User
from app.repositories import AuthorizationRepository


AUTHORIZATION_ERROR_MESSAGE = "Insufficient permissions"


class AuthorizationDeniedError(Exception):
    pass


class AuthorizationService:
    def __init__(self, repository: AuthorizationRepository) -> None:
        self._repository = repository

    async def resolve_active_membership(
        self,
        user: User,
        organization_id: uuid.UUID,
    ) -> OrganizationUser:
        membership = await self._repository.find_membership(
            organization_id,
            user.id,
        )
        if membership is None or not membership.is_active:
            raise AuthorizationDeniedError(AUTHORIZATION_ERROR_MESSAGE)
        return membership

    async def effective_permissions(
        self,
        user: User,
        organization_id: uuid.UUID,
    ) -> frozenset[str]:
        membership = await self.resolve_active_membership(user, organization_id)
        return await self._repository.find_permission_codes(membership.id)

    async def role_slugs(
        self,
        user: User,
        organization_id: uuid.UUID,
    ) -> frozenset[str]:
        membership = await self.resolve_active_membership(user, organization_id)
        return await self._repository.find_role_slugs(membership.id)

    async def require_permission(
        self,
        user: User,
        organization_id: uuid.UUID,
        permission_code: str,
    ) -> OrganizationUser | None:
        if user.is_super_admin:
            return None

        membership = await self.resolve_active_membership(user, organization_id)
        permissions = await self._repository.find_permission_codes(membership.id)
        if permission_code.strip().lower() not in permissions:
            raise AuthorizationDeniedError(AUTHORIZATION_ERROR_MESSAGE)
        return membership

    async def assign_role(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
        role_id: uuid.UUID,
    ) -> OrganizationUserRole:
        membership = await self._repository.find_membership_by_id(membership_id)
        role = await self._repository.find_role_by_id(role_id)

        if (
            membership is None
            or role is None
            or not membership.is_active
            or membership.organization_id != organization_id
            or role.organization_id != organization_id
        ):
            raise AuthorizationDeniedError(AUTHORIZATION_ERROR_MESSAGE)

        assignment = OrganizationUserRole(
            organization_id=organization_id,
            organization_user_id=membership.id,
            role_id=role.id,
        )
        self._repository.add_role_assignment(assignment)
        await self._repository.commit()
        return assignment
