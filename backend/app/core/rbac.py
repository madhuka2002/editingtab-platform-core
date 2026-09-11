"""Minimal Core RBAC definitions without import-time database seeding."""

ORGANIZATION_READ = "organization.read"
ORGANIZATION_MANAGE = "organization.manage"
MEMBERS_READ = "members.read"
MEMBERS_MANAGE = "members.manage"

CORE_PERMISSION_CODES = frozenset(
    {
        ORGANIZATION_READ,
        ORGANIZATION_MANAGE,
        MEMBERS_READ,
        MEMBERS_MANAGE,
    }
)

PREDEFINED_ROLE_PERMISSIONS = {
    "owner": CORE_PERMISSION_CODES,
    "admin": CORE_PERMISSION_CODES,
    "staff": frozenset({ORGANIZATION_READ}),
}
