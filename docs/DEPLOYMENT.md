# Deploying MINDA

MINDA has two parts:

- **API**: FastAPI app in `backend/`. It needs Python 3.12, a PostgreSQL database, and a small persistent disk for uploaded files.
- **Web app**: static files built from `frontend/`. Any static host works.

The steps below use `AUTH_MODE=local`, where MINDA manages passwords itself. That is the mode verified end to end. Supabase Auth is described in the README and is not yet verified against a live project.

## 1. Database

Create an empty PostgreSQL 14+ database (managed Postgres from your host, Neon, or Supabase's Postgres). Use a `postgresql+psycopg://` URL:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
```

Never run `python -m app.seed` against it. The seed wipes every table, and it refuses to run in production or against a database that isn't on the local machine.

## 2. API

Install and migrate:

```bash
cd backend
python -m venv venv && . venv/bin/activate     # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
```

Environment variables (see `backend/.env.example` for every option):

| Variable | Production value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | the PostgreSQL URL above |
| `AUTH_MODE` | `local` |
| `APP_SECRET` | 32+ random characters, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `FRONTEND_URL` | public address of the web app, e.g. `https://minda.example.edu.my` (used in emailed links) |
| `CORS_ORIGINS` | the same address (comma-separate several) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | your mail provider. Without these, invitations and password-reset emails are not sent, and admins see a message saying so. |
| `UPLOAD_DIR`, `PRIVATE_UPLOAD_DIR` | folders on a **persistent** disk (see below) |
| `AI_FEATURES_ENABLED` | `false` unless you add `OPENAI_API_KEY` |

With `ENVIRONMENT=production` the API refuses to start in these cases:

- `APP_SECRET` is shorter than 32 characters.
- The database is SQLite.
- `CORS_ORIGINS` is `*`.
- `FRONTEND_URL` points at localhost.
- `SMTP_HOST` is set without `SMTP_FROM`.

The interactive API docs (`/docs`) are turned off.

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers
```

Run **one** process. Login, posting and other rate limits are kept in memory, so several workers or instances would each keep their own counters. Scaling out needs a shared store first (listed under Not done yet).

Health check: `GET /api/health` returns 200 when the database is reachable and 503 when it isn't.

### Files

- Question images are written to `UPLOAD_DIR` and served publicly at `/uploads/...`.
- Memo attachments are written to `PRIVATE_UPLOAD_DIR` and only served through `/api/memos/{id}/attachments/{id}` after a permission check.

Both folders must survive restarts and redeploys. Hosts with temporary disks need a mounted volume. Back these folders up together with the database.

### First admin and starter content

Public sign-up does not exist. Create the school and its first admin from a shell on the server (the password is prompted for, or read from `MINDA_ADMIN_PASSWORD`, and is never echoed or logged):

```bash
python -m app.cli create-admin --email admin@yourschool.edu.my --name "Puan Admin" --school-name "SMK Your School"
```

Optionally load the starter curriculum: subjects, topics, lessons and sample practice questions. Students see these questions labelled "Sample question", never as SPM past papers. No accounts are created, and the command only runs on a database without subjects.

```bash
python -m app.cli load-curriculum
```

The admin then signs in and does the rest in the app:

1. Academic year and terms (School page).
2. Classes.
3. Teachers and students (one at a time or CSV import), who receive set-password emails.
4. Teaching assignments.

## 3. Web app

```bash
cd frontend
npm ci
VITE_API_URL=https://api.minda.example.edu.my npm run build      # leave VITE_API_URL empty if the API is served from the same origin at /api
```

Upload `frontend/dist/` to a static host. The app uses client-side routing, so the host must serve `index.html` for unknown paths:

- **Netlify**: a `_redirects` file containing `/*  /index.html  200`.
- **Vercel**: `{"rewrites": [{"source": "/(.*)", "destination": "/index.html"}]}` in `vercel.json`.
- **Nginx**: `try_files $uri /index.html;`.

The Supabase variables (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`) stay empty in `AUTH_MODE=local`. Never put a service-role key or any other server secret in a `VITE_` variable, because those end up in the public bundle.

## 4. After deploying

1. `GET https://<api>/api/health` returns `{"status":"ok","database":"ok",...}`.
2. Sign in as the admin, create a teacher and a student, and confirm the set-password emails arrive.
3. Confirm `https://<api>/docs` returns 404, and that `https://<api>/api/admin/overview` returns 401 without signing in (and 403 with a student's token).
4. Publish a memo with a PDF attachment to students. Confirm a student can download it and a teacher can't.

## Updating

```bash
git pull
cd backend && pip install -r requirements.txt && alembic upgrade head   # then restart the API
cd ../frontend && npm ci && npm run build                               # then upload dist/
```

Back up the database and both upload folders before running migrations.

## Not done yet

- A shared rate-limit store, needed before running more than one API process.
- Object storage (e.g. Supabase Storage) instead of local folders. `services/storage.py` is the only place that would change.
- Creating accounts through Supabase Auth from the admin screens (`AUTH_MODE=supabase` returns 501 there).
- No hosting configuration files (Dockerfile, `render.yaml`, `vercel.json`) are included, because the host hasn't been chosen.
