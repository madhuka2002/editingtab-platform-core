# Core API Overview

Base URL for local development:

`http://127.0.0.1:8000`

API prefix:

`/api/v1`

## Authentication

Current authentication area includes login, refresh, logout and current-user organization discovery.

## Organizations

Implemented management areas include:

- organization provisioning
- Super Admin organization listing
- organization detail
- organization status/update
- current user's active organization memberships
- Booking entitlement read

## Members

Implemented areas include:

- member listing
- user creation/attachment
- membership creation/update
- membership role replacement

## Roles

Implemented areas include:

- role listing
- custom role creation
- role update
- role deactivation
- custom role deletion under lifecycle restrictions
- role permission listing/replacement

## Permissions

A global permission catalogue is available to authenticated active users.

Current foundational permissions include organization and member-management permissions.

## Authorization

Authorization is organization scoped.

Super Admin bypass is explicit where policy requires it.

Cross-tenant identifiers must not be usable to access another organization's resources.

## API discovery

For the exact current schemas, open:

`http://127.0.0.1:8000/docs`

Do not treat this overview as a substitute for the live OpenAPI schema.
