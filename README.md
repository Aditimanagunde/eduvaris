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

- **Backend** – FastAPI, SQLAlchemy (SQLite), Pydantic, JWT login, bcrypt, openpyxl. The whole backend is one file: `backend/portal.py`.
- **Frontend** – Next.js, React, Recharts. The whole website is one file: `frontend/app/page.js`.

## Project layout

```
backend/
  portal.py           API, database tables, validation rules, demo data
  requirements.txt
frontend/
  app/page.js         all screens (login, AICTE admin, institution, public check)
  app/layout.js
  package.json
```

## Run the backend

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

### Demo logins

Created by `portal.py seed`. All demo accounts, names and IDs are made up.

| Role | Email | Password |
| --- | --- | --- |
| AICTE admin | `admin@example.com` | `kana143` |
| Institution | `institution1@example.com` to `institution4@example.com` | `Institute@123` |

These are for the local demo only. Change them, and `JWT_SECRET` in `portal.py`, before putting the portal online.

## Run the frontend

Needs Node.js 18.18 or newer. Start the backend first, then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

- Website: http://localhost:3000

The website talks to the API at `http://localhost:8000`. To point it somewhere else, set `NEXT_PUBLIC_API_URL` before starting it.

## Main endpoints

| Area | Endpoints |
| --- | --- |
| Login | `POST /api/auth/token`, `GET /api/auth/me` |
| AICTE admin | `/api/admin/overview`, `/api/admin/issues`, `/api/admin/institutions`, `/api/admin/students` |
| Institution | `/api/institution/overview`, `/api/institution/issues`, `/api/institution/api-key`, `/api/programs`, `/api/students`, `/api/students/upload`, `/api/students/template.csv` |
| Public | `GET /api/verify/{apaar_id}`, `GET /api/health` |

Institution software (ERP) can call the `/api/programs` and `/api/students` endpoints with an `X-API-Key` header.
