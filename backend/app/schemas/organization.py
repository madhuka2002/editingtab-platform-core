import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrganizationProvisionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    owner_user_id: uuid.UUID

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Organization name is required")
        return normalized


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
