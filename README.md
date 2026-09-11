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

## Status

Phase 0 — Foundation