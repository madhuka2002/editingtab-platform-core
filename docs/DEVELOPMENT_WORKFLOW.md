# Development Workflow

## Before Making Changes

1. Read `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, and the relevant scope document.
2. Inspect the repository structure, current Git status, existing implementation, migrations, tests, and configuration.
3. Find and follow the closest existing pattern before introducing a new one.
4. Confirm that the requested capability belongs to Platform Core and supports the current delivery priority.
5. Keep the change focused. Do not combine unrelated cleanup, redesign, or dependency upgrades with feature work.

## Implementation Rules

Use Python, FastAPI, PostgreSQL, SQLAlchemy 2.x, asyncpg, Alembic, and pytest. Maintain the dependency direction:

```text
API -> Service -> Repository -> Database
```

API route handlers must not access the database directly. Use asynchronous database access. PostgreSQL is authoritative for persistent data, and cross-service data access must occur through explicit APIs, events, or connectors rather than another service's database.

## Security Checklist

- Enforce organization isolation for every tenant-owned resource on the server.
- Derive and verify identity, roles, permissions, and entitlements server-side; do not trust client values by themselves.
- Perform authorization for the specific operation and resource.
- Validate all incoming data.
- Use parameterized ORM or database operations.
- Never commit `.env`, passwords, tokens, API keys, secret-bearing connection strings, or private credentials.
- Never log secrets, passwords, access tokens, refresh tokens, or complete third-party credentials.
- Make high-risk operations auditable.
- Add tests for authentication and authorization changes and for tenant isolation.
- Never weaken a security check to make a test pass.

## Database Changes

Every schema change must be represented by an Alembic migration. Do not manually alter a production schema.

For a schema change:

1. Update the model with explicit `nullable`, `unique`, index, and default behavior.
2. Generate an Alembic revision when appropriate.
3. Review the generated operations; do not assume autogeneration is correct.
4. Check data migration, locking, compatibility, constraint, and rollback implications.
5. Provide a valid downgrade where practical.
6. Run the relevant migration and tests in an appropriate development or test environment.

Never delete or rewrite a migration that may already be shared merely to simplify development unless explicitly instructed.

Useful migration inspection command, run from `backend`:

```text
alembic current
```

## Testing

Every meaningful feature needs appropriate tests. New business logic normally requires unit tests. Repository and database behavior should have integration tests where appropriate. Authorization and tenant-isolation paths require positive and negative tests; concurrency-sensitive behavior requires concurrency tests.

Run the project suite from `backend`:

```text
python -m pytest
```

Run relevant focused tests during development, then the broader suite in proportion to the change risk. Never state that tests passed unless they were actually run. Report failures and their context; do not hide, skip, or weaken checks simply to obtain a green result.

Documentation-only changes do not normally require the application test suite unless they alter executable examples or the user requests it. They still require diff and working-tree validation.

## Git and Review

Keep one logical change per logical commit. Do not commit automatically. Use these prefixes:

- `feat:` functionality
- `fix:` bug fix
- `chore:` configuration, setup, or dependencies
- `docs:` documentation
- `test:` tests
- `refactor:` restructuring
- `security:` security work
- `ci:` CI/CD

Before suggesting a commit:

1. Run relevant tests.
2. Inspect `git diff`.
3. Run `git diff --check`.
4. Inspect `git status`.
5. Summarize every changed file and any test or migration result.
6. Suggest a focused commit message, such as `docs: define platform boundaries and Booking V1 scope` for this documentation set.

Never force-push or rewrite history unless explicitly requested. Preserve unrelated user changes in a dirty working tree.
