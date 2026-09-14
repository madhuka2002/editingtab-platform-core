# Platform Core Setup Guide

This guide is for developers and QA engineers cloning `editingtab-platform-core`.

## 1. Prerequisites

Install:

- Git
- Python 3.11 or newer
- PostgreSQL
- A terminal
- Optional: browser for API documentation and local integration checks

## 2. Clone

```bash
git clone https://github.com/madhuka2002/editingtab-platform-core.git
cd editingtab-platform-core
```

## 3. Create the Python environment

```bash
python -m venv backend/.venv
```

Git Bash on Windows:

```bash
source backend/.venv/Scripts/activate
```

## 4. Install dependencies

```bash
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure PostgreSQL

Create a local database:

`editingtab_core`

The application must use the PostgreSQL connection configured in `backend/.env`.

Example structure:

```env
DATABASE_URL=postgresql+asyncpg://<db-user>:<db-password>@localhost:5432/editingtab_core
SECRET_KEY=<local-development-secret>
```

Use the actual configuration fields from the repository if they differ.

Do not commit `.env`.

## 6. Run database migrations

```bash
python -m alembic upgrade head
```

Verify:

```bash
python -m alembic current
```

Expected management baseline:

`6c64c8db15f2`

## 7. Start Core

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

- API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`

## 8. Test the installation

In another terminal, activate the same environment and run:

```bash
cd backend
source .venv/Scripts/activate
python -m pytest -q
```

Also run:

```bash
python -m alembic current
```

## 9. QA account

Do not store QA passwords in Git.

A QA environment should receive a test Super Admin account through a secure process. If a test bootstrap utility is required, keep it outside the committed repository unless it is intentionally part of the product.

## 10. Browser/API acceptance

Core is primarily a backend service. QA can use:

- browser requests through the Admin Web application
- FastAPI docs for development inspection
- automated tests for regression

The main end-user browser flow is implemented in the Booking Admin Web application, not in Core itself.

## 11. Troubleshooting

### Database connection failure

Check:

- PostgreSQL is running
- `editingtab_core` exists
- `.env` is present in `backend`
- connection string is correct
- the PostgreSQL user has access

### Migration failure

Run:

```bash
python -m alembic current
```

Do not manually modify the migration history table to bypass an error.

### Import/module errors

Confirm the virtual environment is active:

```bash
python --version
python -m pip --version
```

Then reinstall:

```bash
pip install -r requirements.txt
```

### Tests fail immediately because of missing packages

Ensure the repository virtual environment is active before running pytest.

## 12. Clean QA principle

QA must record:

- repository commit/tag
- database migration head
- Python version
- PostgreSQL version
- test result
- browser/environment
- exact reproduction steps for defects

Do not report a missing feature as a bug if it is explicitly listed under current limitations.
