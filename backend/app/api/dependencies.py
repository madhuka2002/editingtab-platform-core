import uuid
from datetime import timedelta
from typing import Annotated, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db_session
from app.models import OrganizationUser, User
from app.repositories import (
    AuthorizationRepository,
    EntitlementRepository,
    ProvisioningRepository,
    RefreshTokenRepository,
    UnitOfWork,
    UserRepository,
)
from app.services import (
    AuthService,
    AuthorizationDeniedError,
    AuthorizationService,
    EntitlementService,
    InvalidAuthenticationError,
    OrganizationProvisioningService,
)
from app.services.auth import AUTHENTICATION_ERROR_MESSAGE
from app.services.authorization import AUTHORIZATION_ERROR_MESSAGE


bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthService:
    return AuthService(
        UserRepository(session),
        RefreshTokenRepository(session),
        settings.secret_key,
        timedelta(minutes=settings.access_token_expire_minutes),
        timedelta(days=settings.refresh_token_expire_days),
    )


def get_authorization_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthorizationService:
    return AuthorizationService(AuthorizationRepository(session))


def get_provisioning_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OrganizationProvisioningService:
    unit_of_work = UnitOfWork(session)
    entitlement_service = EntitlementService(
        EntitlementRepository(session),
        unit_of_work,
    )
    return OrganizationProvisioningService(
        ProvisioningRepository(session),
        UserRepository(session),
        entitlement_service,
        unit_of_work,
    )


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTHENTICATION_ERROR_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return await auth_service.get_current_user(credentials.credentials)
    except InvalidAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTHENTICATION_ERROR_MESSAGE,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def require_super_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AUTHORIZATION_ERROR_MESSAGE,
        )
    return current_user


def require_permission(
    permission_code: str,
) -> Callable[..., object]:
    async def permission_dependency(
        organization_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        authorization_service: Annotated[
            AuthorizationService,
            Depends(get_authorization_service),
        ],
    ) -> OrganizationUser | None:
        try:
            return await authorization_service.require_permission(
                current_user,
                organization_id,
                permission_code,
            )
        except AuthorizationDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AUTHORIZATION_ERROR_MESSAGE,
            ) from exc

    return permission_dependency
