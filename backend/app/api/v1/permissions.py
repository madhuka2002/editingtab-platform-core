from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_management_service
from app.models import User
from app.schemas.management import PermissionResponse
from app.services import ManagementService

router = APIRouter(prefix="/permissions", tags=["Permissions"])


@router.get("", response_model=list[PermissionResponse])
async def list_permissions(
    _user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ManagementService, Depends(get_management_service)],
):
    return await service.list_permissions()
