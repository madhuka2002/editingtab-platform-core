from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_provisioning_service, require_super_admin
from app.models import User
from app.schemas import OrganizationProvisionRequest, OrganizationResponse
from app.services import OrganizationProvisioningService, ProvisioningError
from app.services.provisioning import PROVISIONING_ERROR_MESSAGE


router = APIRouter(prefix="/organizations", tags=["Organizations"])


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
