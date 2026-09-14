from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.dependencies import get_auth_service, get_current_user, get_management_service
from app.models import User
from app.schemas import (
    CurrentUserResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.management import CurrentOrganizationResponse
from app.services import AuthService, InvalidAuthenticationError, ManagementService
from app.services.auth import AUTHENTICATION_ERROR_MESSAGE


router = APIRouter(prefix="/auth", tags=["Authentication"])


def authentication_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=AUTHENTICATION_ERROR_MESSAGE,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        access_token, refresh_token, expires_in = await auth_service.login(
            str(request.email),
            request.password,
        )
    except InvalidAuthenticationError as exc:
        raise authentication_exception() from exc
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    """Rotate the supplied refresh token and return its replacement."""
    try:
        access_token, refresh_token, expires_in = await auth_service.refresh(
            request.refresh_token
        )
    except InvalidAuthenticationError as exc:
        raise authentication_exception() from exc
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: LogoutRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Response:
    try:
        await auth_service.logout(request.refresh_token)
    except InvalidAuthenticationError as exc:
        raise authentication_exception() from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(
    user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    return CurrentUserResponse.model_validate(user)


@router.get("/me/organizations", response_model=list[CurrentOrganizationResponse])
async def current_user_organizations(
    user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ManagementService, Depends(get_management_service)],
):
    return await service.current_organizations(user.id)
