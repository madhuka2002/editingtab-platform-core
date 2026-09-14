import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class PageInfo(BaseModel):
    total: int
    limit: int
    offset: int


class OrganizationAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    is_active: bool


class OrganizationListResponse(PageInfo):
    items: list[OrganizationAdminResponse]


class OrganizationUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Organization name is required")
        return value


class CurrentOrganizationResponse(OrganizationAdminResponse):
    membership_id: uuid.UUID
    role_slugs: list[str]


class EntitlementResponse(BaseModel):
    organization_id: uuid.UUID
    module_code: str = "booking"
    is_enabled: bool


class RoleSummary(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_system: bool
    is_active: bool


class MemberResponse(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    is_active: bool
    roles: list[RoleSummary]


class CreateOrganizationUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class AttachMembershipRequest(BaseModel):
    email: EmailStr
    role_ids: list[uuid.UUID] = Field(default_factory=list)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class MembershipStatusRequest(BaseModel):
    is_active: bool


class MembershipStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    is_active: bool


class RoleAssignmentRequest(BaseModel):
    role_ids: list[uuid.UUID]


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    is_system: bool
    is_active: bool


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name", "slug")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value is required")
        return value


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name", "slug")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value is required")
        return value


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    description: str | None


class PermissionAssignmentRequest(BaseModel):
    permission_ids: list[uuid.UUID]
