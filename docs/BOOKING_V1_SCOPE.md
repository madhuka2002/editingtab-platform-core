# Booking V1 Scope

## Objective

Deliver a sellable Booking V1 within 40 days. The deadline requires strict boundaries: complete only the minimum secure Platform Core foundation needed by Booking, then move product development to the separate `editingtab-booking` repository.

This file defines scope and ownership; it does not place Booking implementation in Platform Core.

## Platform Core Exit Criteria

Before switching focus to Booking, Platform Core needs only:

- organizations
- users
- secure authentication
- organization membership
- basic role-based access control
- module and entitlement capability sufficient to authorize Booking use

These capabilities must be secure enough for a multi-tenant production system, but do not need speculative flexibility or features unrelated to Booking V1. Auditability should cover high-risk control-plane operations.

Avoid nonessential Platform Core work before Booking development starts. Examples include elaborate licensing workflows, generalized integration orchestration, advanced administrative reporting, and abstractions built only for possible future modules.

## Booking Service Boundary

Booking is an independently deployable and usable product in `editingtab-booking`, with its own PostgreSQL database. It may consume explicit Core APIs or events for identity, organization context, RBAC, and entitlement checks. It must not query or mutate the Platform Core database, and Platform Core must not query or mutate the Booking database.

Booking should retain sensible product behavior if another optional module is unavailable. Dependencies needed during a request must be explicit, bounded, and handled without cascading unrelated failures.

## Required Booking V1 Capability

Booking V1 must eventually cover:

- property setup
- room types
- physical room and inventory configuration
- basic pricing
- date-based availability
- temporary booking holds
- atomic, concurrency-safe inventory protection
- reservations
- confirmation
- cancellation
- manual, phone, and walk-in bookings
- admin booking management
- public booking flow
- basic notifications
- deployment
- backups and logging
- integration and concurrency testing

Inventory correctness is a release-critical requirement. Holds and reservation confirmation must protect inventory atomically under concurrent requests; a read-then-write availability check without database-backed concurrency protection is not sufficient.

## Explicitly Out of Scope for the 40-Day V1

- Booking.com integration
- Agoda integration
- a full OTA channel manager
- Social Inbox
- a RAG chatbot
- POS
- a native mobile application
- advanced analytics
- loyalty
- CRM
- complex hotel-management functionality

Do not add foundations for these items unless they are also directly required by an in-scope V1 flow. Record useful follow-up ideas in the appropriate product backlog rather than expanding the critical path.

## Scope Decision Test

Before accepting work into the 40-day plan, ask:

1. Is it required to sell, configure, operate, or safely deploy the basic Booking product?
2. Is this the repository that owns the capability and its data?
3. Does postponing it prevent an in-scope end-to-end booking flow or create an unacceptable security, data integrity, recovery, or operational risk?

If the answers do not justify immediate work, defer it. Any scope change should identify what is removed or delayed to preserve the deadline.
