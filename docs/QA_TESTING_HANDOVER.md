# Core QA Testing Handover

## QA purpose

Validate the current Core foundation without assuming that unfinished platform modules are implemented.

## Current baseline

Core currently provides the platform foundation for:

- authentication
- users
- organizations
- memberships
- organization RBAC
- permissions
- Booking entitlement
- Super Admin organization provisioning

## High-priority QA areas

### Authentication

Test:

- valid login
- invalid login
- access to authenticated endpoints
- refresh token flow
- logout/revocation
- inactive user behavior
- password response safety

### Organization provisioning

Super Admin should be able to:

1. Authenticate.
2. Create an organization.
3. Receive the organization identity.
4. Verify the organization is provisioned with the expected foundation roles.
5. Verify the Booking entitlement exists.

### Tenant isolation

Verify:

- organization-scoped users cannot access another organization's members
- cross-tenant role IDs are rejected
- cross-tenant membership IDs are rejected
- organization status affects authorization as designed

### RBAC

Verify:

- owner/admin/staff behavior
- permission checks
- member-management authorization
- role-management authorization
- system-role protections
- custom-role lifecycle

### Owner protections

Verify the system prevents:

- removing the final active owner
- removing the caller's final effective member-management capability
- self-deactivation where policy prohibits it
- invalid final-owner transitions

### Response safety

Verify responses do not expose:

- password hashes
- refresh token secrets
- other credential material

## Expected API semantics

QA should distinguish:

- `401` unauthenticated
- `403` authenticated but unauthorized
- `404` resource not available in the caller's tenant/context
- `409` valid request conflicts with current state
- `422` validation failure

Exact endpoint behavior should be verified against the current API schemas and implementation.

## Regression command

```bash
cd backend
python -m pytest -q
```

Document the exact result rather than relying on this README's historical count.

## Known limitations

The following are not part of the current Core baseline:

- public user signup
- invitation workflow
- password reset workflow
- email verification
- global user search
- Booking-domain permissions
- billing
- complete audit subsystem
- production Core-to-module service identity contract

Do not mark these as regressions.

## Defect report template

```text
Title:
Environment:
Repository commit/tag:
Database migration head:
Browser:
User role:
Organization:
Preconditions:
Steps to reproduce:
Expected result:
Actual result:
Screenshots/logs:
Severity:
```
