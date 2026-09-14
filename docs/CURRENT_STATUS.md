# Core Current Status

## Completed

- Repository foundation
- FastAPI application
- Health endpoint
- Async PostgreSQL foundation
- Alembic
- Users
- Organizations
- Memberships
- Authentication
- RBAC
- Booking entitlement
- Organization provisioning
- Organization/member/role management
- Owner protection
- Tenant-safe authorization
- Role active state migration

## Migration

Current documented management migration:

`6c64c8db15f2`

## Automated test baseline

Historical implementation verification:

`72 passed, 2 warnings`

Always rerun tests for the current checkout.

## Not complete

- Public signup
- Invitation workflow
- Password reset
- Email verification
- Full audit subsystem
- Billing
- Booking-domain permissions
- Production service-to-service identity contract

## Relationship to Booking

Booking owns tourism inventory and booking-domain data.

Core owns identity, organization membership, authorization and module entitlement.

The two services must not share internal database access.
