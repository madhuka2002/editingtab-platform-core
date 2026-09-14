# Core Architecture Status

## Boundary

Core is the identity and authorization foundation.

```text
Admin Web / Product Module
          |
          v
        Core API
          |
       Service
          |
     Repository
          |
      PostgreSQL
```

## Data owned by Core

- users
- organizations
- memberships
- roles
- permissions
- role assignments
- module entitlements
- authentication state

## Data explicitly outside Core

- properties
- room types
- physical rooms
- availability
- reservations
- social conversations
- POS data
- chatbot knowledge

## Modularity rule

Every primary product module should be independently deployable, independently usable and independently maintainable.

Cross-module functionality must use explicit APIs, events or connectors.

No module should depend on another module's internal database.

## Current security boundary

Core authorization is organization-scoped.

The current Booking development integration still requires a future trusted service-to-service identity contract. A manually supplied organization header is development context only and must not be considered production authorization.

## Database isolation

Tenant-scoped relationships use organization-aware constraints where required.

Foreign-key behavior is intentionally restrictive for important identity records.

## Current status

The Core foundation is implemented sufficiently to support continued Booking/Admin development, but production hardening and a formal service-to-service identity contract remain required before treating the integrated platform as production-ready.
