# Repository Guide

`editingtab-platform-core` is the shared control-plane service for the EditingTab platform. Keep it small, secure, and independent from product-specific services.

## Read First

- [README.md](README.md) for the repository overview and current status.
- [ARCHITECTURE.md](ARCHITECTURE.md) for service boundaries, ownership, and dependency direction.
- [docs/BOOKING_V1_SCOPE.md](docs/BOOKING_V1_SCOPE.md) for the 40-day delivery boundary.
- [docs/DEVELOPMENT_WORKFLOW.md](docs/DEVELOPMENT_WORKFLOW.md) for security, migrations, tests, and Git practices.
- `backend/tests/` for executable examples and expected behavior.

## Working Rules

- Inspect existing code, migrations, tests, configuration, and Git status before changing anything.
- Follow existing patterns before introducing new ones.
- Keep changes limited to the current task; do not redesign the architecture unless specifically asked.
- Preserve the dependency direction: API -> Service -> Repository -> Database.
- Keep product data and logic, including Booking, Social, Chatbot, and POS concerns, out of Platform Core.
- Never access another service's database. Use explicit APIs, events, or connectors.
- Enforce tenant isolation and authorization server-side, and never commit secrets.
- Use Alembic for every schema change. Do not rewrite an already-shared migration unless explicitly instructed.
- Add appropriate tests for meaningful behavior, especially authentication, authorization, and tenant isolation.
- Do not commit automatically.

## Common Commands

Run backend commands from the repository root:

```text
cd backend
python -m pytest
alembic current
```

Before suggesting a commit, run relevant tests, inspect `git diff` and `git status`, summarize the changed files, and propose one conventional commit message.
