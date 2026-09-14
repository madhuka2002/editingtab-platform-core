# EditingTab Platform Core

Core identity, organization, authentication, authorization and entitlement service for the Editing Tab modular tourism operations platform.

## Purpose

`editingtab-platform-core` provides the shared platform foundation used by independently deployable product modules.

Core owns:

- Users
- Organizations
- Organization memberships
- Authentication and refresh-token lifecycle
- Organization-scoped roles
- Permission catalogue
- Role/permission assignments
- Module entitlements
- Super Admin organization provisioning
- Core authorization policies

Core does **not** own:

- Hotel properties
- Room types or physical rooms
- Availability
- Reservations
- Social-media messages
- POS products
- Chatbot knowledge
- OTA booking data

Product modules must communicate through explicit APIs, events and connectors rather than directly accessing Core's database.

## Current implementation status

Implemented baseline:

- FastAPI backend
- PostgreSQL database
- SQLAlchemy async database foundation
- Alembic migrations
- JWT access authentication
- Refresh-token rotation
- Argon2 password hashing
- Organization provisioning
- Organization-scoped RBAC
- Super Admin authorization
- Booking module entitlement
- Organization/member management APIs
- Role management APIs
- Permission catalogue APIs
- Tenant-safe database constraints
- Owner/self-lockout protections
- Inactive-organization authorization protection

The current management release includes migration:

`6c64c8db15f2_add_role_active_state.py`

Expected automated test baseline at the time of this documentation:

`72 passed, 2 warnings`

Do not treat this document as a claim that the complete tourism platform is production-ready. Booking, availability, OTA/channel integrations, payments and other modules remain separate development scope.

## Technology

- Python
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic Settings
- JWT
- Argon2 password hashing

## Repository setup

### Prerequisites

Install:

- Git
- Python 3.11+ recommended for development
- PostgreSQL
- A terminal capable of running the commands below

The project should be run from the repository root unless a command explicitly says otherwise.

### Clone

```bash
git clone https://github.com/madhuka2002/editingtab-platform-core.git
cd editingtab-platform-core
```

### Create and activate the virtual environment

Git Bash on Windows:

```bash
python -m venv backend/.venv
source backend/.venv/Scripts/activate
```

If `source` is unavailable, activate the virtual environment using the appropriate command for your shell.

### Install dependencies

```bash
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Environment configuration

Create:

`backend/.env`

Do not commit this file.

Use the project's configuration fields as the source of truth. At minimum, configure the PostgreSQL connection and application secret values required by the installed configuration.

Example shape only:

```env
DATABASE_URL=postgresql+asyncpg://<db-user>:<db-password>@localhost:5432/editingtab_core
SECRET_KEY=<development-secret>
```

Never put real credentials in Git.

### Create the database

Create a PostgreSQL database named:

`editingtab_core`

For a local PostgreSQL installation, the database can be created with your normal PostgreSQL administration tool or `createdb`.

Do not copy passwords from this document into production.

### Run migrations

From `backend`:

```bash
python -m alembic upgrade head
```

Verify the current migration:

```bash
python -m alembic current
```

The documented management baseline expects:

`6c64c8db15f2 (head)`

### Start the API

From `backend`:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Local API:

`http://127.0.0.1:8000`

FastAPI documentation:

`http://127.0.0.1:8000/docs`

Do not use Swagger as a substitute for browser product acceptance testing. Swagger is useful for API inspection and development.

## Run tests

From `backend`:

```bash
python -m pytest -q
```

The current documented baseline was 72 passing tests. Test counts can change as development continues.

Useful validation:

```bash
python -m alembic current
python -m pytest -q
git diff --check
```

## Core API areas currently implemented

### Authentication

- Login
- Access-token authentication
- Refresh-token rotation
- Logout/revocation
- Current-user organization discovery

### Organization management

- Super Admin organization list
- Super Admin organization detail
- Super Admin organization status/update
- Organization provisioning

### Membership management

- Member listing
- User creation/attachment
- Membership creation/update
- Role assignment

### RBAC

- Role listing
- Custom role creation
- Role updates
- Role deactivation/deletion rules
- Permission catalogue
- Role permission management

### Entitlements

- Organization Booking entitlement read

## Security rules currently implemented

The Core implementation includes:

- Password hashing rather than plaintext storage
- No password hashes in API responses
- No refresh-token secrets in API responses
- Organization-scoped queries
- Cross-tenant resource protection
- Explicit 401/403 authorization handling
- Super Admin bypass where defined by policy
- Inactive organization blocking for ordinary organization authorization
- At least one active owner protection
- Self-deactivation protection
- Final-owner role removal protection
- Protection against removing the caller's final effective `members.manage` capability
- System-role protection
- Custom-role deactivation/deletion safeguards
- Database composite constraints supporting tenant isolation

## Important development limitation

The current Booking integration uses development-only organization context handling. A development `X-Organization-ID` header must **not** be treated as production authorization.

Production service-to-service identity must use a trusted Core-to-Booking authentication/authorization contract.

## QA

QA should test an exact Git commit/tag rather than an unpinned moving `main` branch.

See:

- `docs/SETUP.md`
- `docs/QA_TESTING_HANDOVER.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/ARCHITECTURE_STATUS.md`
- `docs/API_OVERVIEW.md`
- `docs/CURRENT_STATUS.md`

## Security

Never commit:

- `.env`
- passwords
- JWT secrets
- API keys
- private keys
- production database credentials
- customer data

If a secret is accidentally committed, rotate it immediately.

## License

Internal Editing Tab project. Licensing and redistribution terms are controlled by the project owner.
