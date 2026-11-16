# Eduvaris

APAAR ID-based student data management and verification platform for AICTE-approved institutions.
Built for Smart India Hackathon 2026, Problem Statement 26263.

## Who uses it

- **AICTE admin** – adds institutions, sees every institution's data, dashboards and flagged problems.
- **Institution** – adds programs (with approved intake), submits student data by form, Excel/CSV upload or API, and fixes flagged problems.
- **Public** – can check whether an APAAR ID is enrolled at an AICTE-approved institution.

## What it checks automatically

- Admissions exceeding approved intake or supernumerary seats
- The same APAAR ID enrolled at more than one institution
- The same APAAR ID registered with a different name or date of birth
- Inconsistent student data (for example NRI and Foreign National together)

## Tech stack

FastAPI, SQLAlchemy (SQLite), Pydantic, JWT login, bcrypt, openpyxl. The whole backend is one file: `backend/portal.py`.

## Run it

Needs Python 3.10 or newer.

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe portal.py seed    # creates the database + demo data (run once)
.\.venv\Scripts\python.exe portal.py         # starts the API

# macOS / Linux
.venv/bin/pip install -r requirements.txt
.venv/bin/python portal.py seed
.venv/bin/python portal.py
```

- API: http://localhost:8000
- Interactive API docs: http://localhost:8000/docs

`portal.py seed` prints the demo logins. All demo names and IDs are made up.

## Main endpoints

| Area | Endpoints |
| --- | --- |
| Login | `POST /api/auth/token`, `GET /api/auth/me` |
| AICTE admin | `/api/admin/overview`, `/api/admin/issues`, `/api/admin/institutions`, `/api/admin/students` |
| Institution | `/api/institution/overview`, `/api/institution/issues`, `/api/institution/api-key`, `/api/programs`, `/api/students`, `/api/students/upload`, `/api/students/template.csv` |
| Public | `GET /api/verify/{apaar_id}`, `GET /api/health` |

Institution software (ERP) can call the `/api/programs` and `/api/students` endpoints with an `X-API-Key` header.
