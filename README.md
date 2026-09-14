# EditingTab Platform Core

Platform Core is the shared control-plane service for the EditingTab modular software ecosystem.

It is responsible for platform-level capabilities such as:

- Organizations
- Users and employees
- Authentication
- Roles and permissions
- Module activation and licensing
- Platform administration
- Audit logging

## Architecture Principle

Platform Core must not contain product-specific business logic.

Booking, Social, Chatbot, POS, and other product modules are independently deployable services with their own repositories and data ownership.

Communication between services must occur through explicit APIs, events, and defined contracts. Services must never directly access another service's database.

## Core management API

Platform Super Admins can list, inspect, rename, deactivate, and reactivate
organizations through `/api/v1/organizations`. Organization members discover
their active memberships through `/api/v1/auth/me/organizations`.

Organization-scoped member, role, permission, and Booking-entitlement operations
use the existing server-side RBAC dependencies. Mutations are atomic and tenant
scoped, and they protect predefined roles and the last active owner. Organizations,
users, and memberships are not exposed through administrative hard-delete APIs.

## Status

Phase 0 — Foundation
