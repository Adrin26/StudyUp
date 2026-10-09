# MINDA — Learn. Practice. Master.

MINDA is a school learning and academic management platform for Malaysian secondary schools (Form 1–5, SPM). It grew out of the StudyUp prototype and keeps its learning flow. Students learn a topic through short interactive slides, take a 10-question quiz, and see their mastery move. They can practise SPM-style questions and discuss in a school-scoped community. Teachers see which students and topics need attention, assign targeted practice, and generate exams from the question bank. Admins manage the school.

There are exactly three roles: **Admin**, **Teacher** and **Student**. "Class teacher" and "subject teacher" are not roles. They are derived from a teacher's class and subject assignments.

The architecture, ERD, permission matrix, API outline and the phased delivery plan are in [`docs/PLAN.md`](docs/PLAN.md). **Phase 1 (Foundation) is implemented**; later phases are listed there.

> **About the question bank:** the seeded questions are *SPM-style samples* generated for this demo, tagged with years 2019–2024 for filtering. They are **not** real SPM past-year papers.

## Quick start (local)

Requirements: Python 3.11+, Node 20+, and PostgreSQL 15+ (or SQLite for a quick look).

```powershell
# Backend
cd backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then set DATABASE_URL (see below)
venv\Scripts\alembic upgrade head    # PostgreSQL only; SQLite tables are created automatically
venv\Scripts\python -m app.seed      # DEMO DATA: wipes the database and loads a fictional school
venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                     # http://localhost:5173
```

For local PostgreSQL, create the database once (`createdb -U postgres studyup_db`) and set:

```
DATABASE_URL=postgresql+psycopg://postgres:<password>@localhost:5432/studyup_db
AUTH_MODE=local
```

Vite proxies `/api` to `http://127.0.0.1:8000`. API docs: http://127.0.0.1:8000/docs.

### Database migrations

Alembic (`backend/migrations`) is the source of truth for the schema on PostgreSQL:

| Revision | Contents |
| --- | --- |
| `0001` | Baseline: the original StudyUp schema |
| `0002` | Phase 1: account `status`, `username`, `last_login_at`, `local_credentials`, `password_reset_tokens`, `audit_logs`; removes the stored `teacher_types` |

```powershell
venv\Scripts\alembic upgrade head      # apply
venv\Scripts\alembic current           # show revision
venv\Scripts\alembic check             # models and database agree
```

The seed resets the schema by running the migrations, so a seeded database is always at `head`. The app does not create tables on PostgreSQL. If migrations haven't been applied, it logs a warning on startup.

### Demo accounts (development only, password `demo1234`)

All seeded people, schools and results are **fictional demo data**. The login page lists these accounts only when `ENVIRONMENT=development` and `AUTH_MODE=local`.

| Account | Username | Role |
| --- | --- | --- |
| `admin@school.demo` | `admin` | Admin of SMK Taman Ilmu |
| `aisyah@student.demo` | `aisyah` | Student, Form 4 Bestari (active streak, weak Quadratic Equations, pending assignment) |
| `farid@teacher.demo` | `farid` | Teacher: class teacher of 4 Bestari, Mathematics / Add Maths |
| `rohana@teacher.demo` | `rohana` | Teacher: class teacher of 4 Cemerlang, Biology / History |
| `tan@teacher.demo` | `tan` | Teacher: subject teacher only (Physics, Chemistry, English) |

Users sign in with **email or username**. Every student is `<firstname>@student.demo`.

### Creating a real admin

Public self-registration is off, and no request can grant the Admin role. Provision admins from the server:

```powershell
cd backend
venv\Scripts\python -m app.cli create-admin --email head@school.edu.my --name "Puan Head" --school-name "SMK Contoh"
# prompts for the password (or reads MINDA_ADMIN_PASSWORD); it is stored only as a scrypt hash

venv\Scripts\python -m app.cli grant-admin --email existing@school.edu.my
```

Both commands write an entry to the audit log.

## Authentication (Phase 1)

`AUTH_MODE` selects the identity provider. The FastAPI permission checks are the same in both modes.

- **`local`** (development / self-hosted): passwords are hashed with scrypt in `local_credentials`. FastAPI issues short-lived HS256 tokens. Tokens carry a password-version claim, so changing or resetting a password signs out every other session.
- **`supabase`**: Supabase Auth issues tokens and FastAPI verifies them (JWT secret or JWKS). Password recovery uses Supabase's email flow.

Security behaviour:

- A login failure always shows the same message ("Incorrect email/username or password"), whether or not the account exists.
- Login, forgot-password, reset and change-password are rate-limited per IP and per account (`LOGIN_MAX_FAILURES` failures in `LOGIN_WINDOW_MINUTES`).
- **Disabled** accounts are refused at login and on every request, including requests that present a token issued before the account was disabled.
- Password policy: 8–128 characters, at least one letter and one digit, and not the same as the email or username.
- Password reset tokens are single-use and expire after `PASSWORD_RESET_TTL_MINUTES` (default 30). Only their SHA-256 hash is stored. In development the reset link is **printed to the API console**; no email provider is wired up yet.
- Passwords are never returned, logged, or written to the audit log. The audit log strips password and token fields from its details.
- Role checks live in `app/permissions.py` (`require_admin`, `require_teacher`, `require_student`, …). The frontend route guards are for UX only.

## AI features (optional, off by default)

The MVP does not depend on AI. With `AI_FEATURES_ENABLED=false` (the default):

- every `/api/ai/*` endpoint returns 404;
- the UI hides all AI entry points (lesson help, hints, explanations, "Why these?", teaching ideas).

With `AI_FEATURES_ENABLED=true`, AI calls go through the backend only. Set `OPENAI_API_KEY` to use OpenAI. Without a key, the features return deterministic fallbacks.

## Tests

```powershell
cd backend
venv\Scripts\python -m pytest -q
```

The tests run against an isolated SQLite database. They cover:

- login by email or username, and the generic failure message;
- rate limiting;
- disabled accounts, role guards and admin school scoping;
- derived teacher responsibilities;
- forgot, reset and change password, the password policy, and token invalidation;
- audit logging, and the admin CLI;
- the AI flag;
- the migration chain: upgrade, a no-drift check, and downgrade;
- the existing learning, quiz, practice and exam flows.

Frontend: `cd frontend && npm run build` (type-checks and builds).

## Architecture

```
frontend/   React + TypeScript + Vite + Tailwind v4 + shadcn-style UI + Recharts
            TanStack Query, React Hook Form + Zod, React Router
backend/    FastAPI + SQLAlchemy 2 + Pydantic + Alembic
  app/permissions.py  centralised role guards
  app/routers/        HTTP endpoints (auth, admin, subjects, lessons, quiz, practice, exams, teachers, community, ai)
  app/services/       business logic: access scoping, passwords, rate limiting, audit, mastery, ...
  app/cli.py          protected admin commands
  app/seed/           DEMO DATA: curriculum, lessons, question generators, simulated history
  migrations/         Alembic revisions
supabase/migrations/  RLS policies and helpers for the Supabase deployment
docs/PLAN.md          architecture, ERD, permission matrix, API outline, phases
```

### What is deterministic

All grading, scoring, mastery, randomization, exam generation, recommendations and analytics run in Python (`backend/app/services`).

- **Mastery** (`services/mastery.py`): `evidence × (0.7 × recent + 0.3 × historical)`. *Recent* is difficulty-weighted accuracy over the last 10 attempts. *Evidence* ramps from 0.5 to 1 over the first 10 attempts. Levels: 0–39 Needs Attention, 40–59 Developing, 60–79 Good, 80–100 Mastered.
- **Randomization** (`services/randomizer.py`): a seeded `random.Random`, so a practice set or exam can be reproduced from its stored seed.
- **Recommendations** (`services/recommendations.py`): rule-based (pending assignment, then weak topics, then an unfinished lesson, then the next topic).
- **Intervention alerts** (`services/analytics.py`): a topic is flagged when at least `max(3, class_size / 4)` students are below 50% mastery.

### Authorization

The backend checks every request, independent of the UI:

- **Admin**: only their own school's records (overview, audit log).
- **Student**: only their own progress.
- **Teacher**: as **class teacher**, every subject for students in their homeroom class; as **subject teacher**, only their subject, and only for the classes they teach. A teacher can be both. Responsibilities are computed from `classes.class_teacher_id` and `teacher_subjects` (`services/access.py`).

On Supabase, the same rules are enforced again with RLS (`supabase/migrations/`). Progress, attempt and audit tables are writable only through the backend.

## Using Supabase

1. Create a Supabase project. Run `supabase/migrations/0001_schema.sql` in the SQL editor.
2. Backend `.env`:
   ```
   AUTH_MODE=supabase
   DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_JWT_SECRET=<legacy JWT secret>   # or leave empty to verify via JWKS
   ```
3. `cd backend && alembic stamp 0001 && alembic upgrade head`, then run `supabase/migrations/0002_phase1_auth_rls.sql`.
4. Frontend `.env`: `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (the anon key only; never the service-role key).
5. Disable public sign-ups in Supabase Auth settings. Accounts that are created anyway become students (trigger `handle_new_user`). Grant admin with `python -m app.cli grant-admin`.

The demo seed refuses to run with `AUTH_MODE=supabase`, against a Supabase URL, or in production.

> The Supabase path has not yet been verified against a live Supabase project; Phase 1 was verified with local PostgreSQL.

## Deployment notes

- **Frontend**: `npm run build` produces a static `frontend/dist`. Set `VITE_API_URL` if the API isn't served from the same origin at `/api`.
- **Backend**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Run `alembic upgrade head` on deploy. With `ENVIRONMENT=production` the app refuses to start without an `APP_SECRET` of 32+ characters or with SQLite. Set `CORS_ORIGINS` to the frontend URL.
- The login rate limiter is in-process. Behind several workers or instances, replace it with a shared store (e.g. Redis).

## Roadmap

See [`docs/PLAN.md`](docs/PLAN.md). Phase 2 onward covers:

- admin user, class and subject management, and the school calendar;
- homework and assessments, and announcements;
- reports and analytics;
- the moved-over learning features;
- the optional AI services.
