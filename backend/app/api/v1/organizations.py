import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_current_user, get_management_service, get_provisioning_service, require_permission, require_super_admin
from app.core.rbac import MEMBERS_MANAGE, MEMBERS_READ, ORGANIZATION_READ
from app.models import OrganizationUser, User
from app.schemas.management import (
    AttachMembershipRequest, CreateOrganizationUserRequest, EntitlementResponse,
    MemberResponse, MembershipStatusRequest, MembershipStatusResponse,
    OrganizationAdminResponse, OrganizationListResponse, OrganizationUpdateRequest,
    PermissionAssignmentRequest, PermissionResponse, RoleAssignmentRequest,
    RoleCreateRequest, RoleResponse, RoleUpdateRequest,
)
from app.schemas import OrganizationProvisionRequest, OrganizationResponse
from app.services import ManagementConflictError, ManagementNotFoundError, ManagementService, OrganizationProvisioningService, ProvisioningError
from app.services.provisioning import PROVISIONING_ERROR_MESSAGE


router = APIRouter(prefix="/organizations", tags=["Organizations"])


def management_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ManagementNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    _admin: Annotated[User, Depends(require_super_admin)],
    service: Annotated[ManagementService, Depends(get_management_service)],
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    active: bool | None = None, search: str | None = Query(default=None, max_length=100),
) -> OrganizationListResponse:
    items, total = await service.list_organizations(limit, offset, active, search)
    return OrganizationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def provision_organization(
    request: OrganizationProvisionRequest,
    _super_admin: Annotated[User, Depends(require_super_admin)],
    service: Annotated[
        OrganizationProvisioningService,
        Depends(get_provisioning_service),
    ],
) -> OrganizationResponse:
    try:
        organization = await service.provision(
            request.name,
            request.owner_user_id,
        )
    except ProvisioningError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=PROVISIONING_ERROR_MESSAGE,
        ) from exc
    return OrganizationResponse.model_validate(organization)


@router.get("/{organization_id}", response_model=OrganizationAdminResponse)
async def organization_detail(organization_id: uuid.UUID, _admin: Annotated[User, Depends(require_super_admin)], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.organization(organization_id)
    except ManagementNotFoundError as exc:
        raise management_error(exc) from exc


@router.patch("/{organization_id}", response_model=OrganizationAdminResponse)
async def update_organization(organization_id: uuid.UUID, request: OrganizationUpdateRequest, _admin: Annotated[User, Depends(require_super_admin)], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.update_organization(organization_id, name=request.name, is_active=request.is_active)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.get("/{organization_id}/entitlements/booking", response_model=EntitlementResponse)
async def booking_entitlement(organization_id: uuid.UUID, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(ORGANIZATION_READ))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        enabled = await service.booking_entitlement(organization_id)
        return EntitlementResponse(organization_id=organization_id, is_enabled=enabled)
    except ManagementNotFoundError as exc:
        raise management_error(exc) from exc


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
async def list_members(organization_id: uuid.UUID, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_READ))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.list_members(organization_id)
    except ManagementNotFoundError as exc:
        raise management_error(exc) from exc


@router.post("/{organization_id}/users", response_model=MemberResponse, status_code=201)
async def create_user_membership(organization_id: uuid.UUID, request: CreateOrganizationUserRequest, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.create_user_membership(organization_id, email=str(request.email), password=request.password, first_name=request.first_name, last_name=request.last_name, role_ids=request.role_ids)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.post("/{organization_id}/memberships", response_model=MemberResponse, status_code=201)
async def attach_membership(organization_id: uuid.UUID, request: AttachMembershipRequest, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.attach_membership(organization_id, email=str(request.email), role_ids=request.role_ids)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.patch("/{organization_id}/memberships/{membership_id}", response_model=MembershipStatusResponse)
async def update_membership(
    organization_id: uuid.UUID, membership_id: uuid.UUID, request: MembershipStatusRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))],
    service: Annotated[ManagementService, Depends(get_management_service)],
):
    try:
        return await service.set_membership_active(organization_id, membership_id, request.is_active, current_user.id)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.put("/{organization_id}/memberships/{membership_id}/roles", response_model=list[RoleResponse])
async def replace_membership_roles(
    organization_id: uuid.UUID, membership_id: uuid.UUID, request: RoleAssignmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))],
    service: Annotated[ManagementService, Depends(get_management_service)],
):
    try:
        return await service.replace_membership_roles(organization_id, membership_id, request.role_ids, current_user.id)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.get("/{organization_id}/roles", response_model=list[RoleResponse])
async def list_roles(organization_id: uuid.UUID, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_READ))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.list_roles(organization_id)
    except ManagementNotFoundError as exc:
        raise management_error(exc) from exc


@router.post("/{organization_id}/roles", response_model=RoleResponse, status_code=201)
async def create_role(organization_id: uuid.UUID, request: RoleCreateRequest, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.create_role(organization_id, name=request.name, slug=request.slug, description=request.description)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.patch("/{organization_id}/roles/{role_id}", response_model=RoleResponse)
async def update_role(organization_id: uuid.UUID, role_id: uuid.UUID, request: RoleUpdateRequest, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.update_role(organization_id, role_id, **request.model_dump(exclude_unset=True))
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.delete("/{organization_id}/roles/{role_id}", status_code=204)
async def delete_role(organization_id: uuid.UUID, role_id: uuid.UUID, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        await service.delete_role(organization_id, role_id)
        return Response(status_code=204)
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc


@router.get("/{organization_id}/roles/{role_id}/permissions", response_model=list[PermissionResponse])
async def role_permissions(organization_id: uuid.UUID, role_id: uuid.UUID, _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_READ))], service: Annotated[ManagementService, Depends(get_management_service)]):
    try:
        return await service.role_permissions(organization_id, role_id)
    except ManagementNotFoundError as exc:
        raise management_error(exc) from exc


@router.put("/{organization_id}/roles/{role_id}/permissions", response_model=list[PermissionResponse])
async def replace_role_permissions(
    organization_id: uuid.UUID,
    role_id: uuid.UUID,
    request: PermissionAssignmentRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    _authorized: Annotated[OrganizationUser | None, Depends(require_permission(MEMBERS_MANAGE))],
    service: Annotated[ManagementService, Depends(get_management_service)],
):
    try:
        return await service.replace_role_permissions(
            organization_id,
            role_id,
            request.permission_ids,
            current_user.id,
        )
    except (ManagementNotFoundError, ManagementConflictError) as exc:
        raise management_error(exc) from exc
