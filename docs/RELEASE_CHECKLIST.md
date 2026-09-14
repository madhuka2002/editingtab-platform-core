# Core Release Checklist

## Repository

- [ ] Working tree reviewed
- [ ] Intended commit identified
- [ ] QA tag/release created
- [ ] QA uses exact commit/tag

## Environment

- [ ] Python version recorded
- [ ] PostgreSQL version recorded
- [ ] Environment variables documented without secrets
- [ ] Database name documented

## Database

- [ ] `alembic upgrade head` succeeds
- [ ] `alembic current` verified
- [ ] Migration head recorded
- [ ] Backup/restore plan exists for shared environments

## Automated tests

- [ ] `python -m pytest -q` passes
- [ ] `git diff --check` passes
- [ ] No credentials committed

## Security

- [ ] `.env` ignored
- [ ] Secrets rotated if exposed
- [ ] Password hashes never returned
- [ ] Refresh-token secrets never returned
- [ ] Tenant boundaries tested
- [ ] Owner/self-lockout protections tested

## QA

- [ ] QA handover updated
- [ ] Known limitations updated
- [ ] Browser UAT dependencies documented
- [ ] Defect template available
