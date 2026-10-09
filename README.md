# MINDA — Learn. Practice. Master.

MINDA is a school learning and academic management platform for Malaysian secondary schools (Form 1–5, SPM). It grew out of the StudyUp prototype and keeps its learning flow. Students learn a topic through short interactive slides, take a 10-question quiz, and see their mastery move. They can practise SPM-style questions and discuss in a school-scoped community. Teachers see which students and topics need attention, assign targeted practice, and generate exams from the question bank. Admins manage the school.

There are exactly three roles: **Admin**, **Teacher** and **Student**. "Class teacher" and "subject teacher" are not roles. They are derived from a teacher's class and subject assignments.

The architecture, ERD, permission matrix, API outline and the phased delivery plan are in [`docs/PLAN.md`](docs/PLAN.md). **Phases 1–3 are implemented** (foundation, school administration, content and memos); later phases are listed there.

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
| `0003` | Phase 2: school profile fields, `academic_years`, `academic_terms`, `classes.academic_year_id` + `status` (replaces `year`; existing classes are moved into a backfilled year per school and calendar year), enrolment `status`/`enrolled_at`/`left_at`, student and staff IDs, department |
| `0004` | Phase 3: content `status` on subjects, topics and lessons; subtopics, objectives, prerequisites, subject form levels; question `form` and `attribution` (`pending_review` becomes `draft`, `rejected` becomes `archived`); school memos, attachments, reads and acknowledgements |
| `0005` | Phase 4: one scored answer per student, question set and question |
| `0006` | Phase 5: assignment `available_from` and `feedback_release`; `exam_publications`, `exam_attempts`, `exam_answers` |
| `0007` | Phase 6: post/comment moderation `status`, comment `parent_id`, `post_bookmarks`, `content_reports`, `student_xp_events` (existing XP becomes an opening balance), `calendar_events` |

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
| `zara@student.demo` | `zara` | Student not yet in a class, for trying enrolment |

Users sign in with **email or username**. Every student is `<firstname>@student.demo`. The seed also creates the current academic year with two terms whose dates are approximate demo values, not an official school calendar.

### Creating a real admin

Public self-registration is off, and no request can grant the Admin role. Provision admins from the server:

```powershell
cd backend
venv\Scripts\python -m app.cli create-admin --email head@school.edu.my --name "Puan Head" --school-name "SMK Contoh"
# prompts for the password (or reads MINDA_ADMIN_PASSWORD); it is stored only as a scrypt hash

venv\Scripts\python -m app.cli grant-admin --email existing@school.edu.my

# optional, on a database with no subjects yet: starter subjects, lessons and sample questions (no accounts)
venv\Scripts\python -m app.cli load-curriculum
```

All three commands write an entry to the audit log.

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

## School administration (Phase 2)

Admins manage their own school from the web app; every rule is enforced by the API (`/api/admin/*`, see `docs/PLAN.md` §6):

- **Dashboard**: current academic year, summary counts, quick actions, alerts that link to the fix (no current year, students without a class, teachers without assignments, classes without a class teacher), content completion per subject, recent accounts and activity.
- **Users**: searchable, filterable, paginated directory; create students (Student ID, form, class, subjects) and teachers (Staff ID, department, teaching assignments); edit; disable and reactivate; send a set-password link.
- **No admin ever sees or sets a password.** New accounts are created without one. The admin can send a single-use set-password link that expires after `INVITE_TTL_HOURS` (default 72); only its hash is stored. In development the link is **printed to the API console**, because no email provider is configured. Disabling an account voids its unused links.
- **CSV import** (`/admin/users/import`): columns `role, full_name, email` plus optional `username, student_number, staff_number, form, class, department`, up to 500 rows. The preview validates headers and every row and flags duplicates inside the file and against existing accounts. Confirm creates only the valid rows and reports the rest. The page offers a downloadable template.
- **School profile**: name, logo (an `https://` URL), address, phone, email, timezone, description. The logo and name appear in the navigation.
- **Academic years and terms**: one current year per school, and terms must sit inside their year without overlapping.
- **Classes**: create per academic year (the name must be unique in that year), set the form and class teacher, enrol (bulk), transfer within the same year, withdraw, and archive or restore. Enrolments are never deleted: transfers and withdrawals close the row (`status`, `left_at`), so the roster history is kept. A student can be in at most one class per academic year.
- **Teaching assignments**: teacher × subject × class. Archived classes and ended enrolments no longer give a teacher access to students.
- Admin accounts can't be modified through these screens; use the CLI below.

## Teacher tools (Phase 5)

- **Assignment windows**: an assignment can have an opening time (`available_from`) and a due date. Before it opens, students can't load it; after the due date, no new answers are accepted.
- **Answer release for assignments**: "Show answers" is either *after each question* (the default, as before) or *after the due date*. When answers are held, the API returns only "answer saved". It also holds back correctness, the correct answer, explanation, score, XP, badges and mastery changes, and the AI explain/answer-check endpoints refuse those questions. Held answers never earn XP.
- **Online exams**: on a saved exam, *Publish to class* opens it to one class with an open/close window, an optional time limit and an answer-release time (which must be after closing). Only the class teacher, or a teacher assigned that subject in that class, can publish. Students of that class find it under **Exams**. Each answer is final once saved. An attempt left open is submitted automatically at the deadline. Marks, correct answers and explanations appear only after the release time. Exam answers are stored separately (`exam_answers`) and do not affect XP or mastery.
- **Results**: the teacher sees each student's status and marks per class as soon as they submit. Once students have started, the schedule can't change and the exam can't be deleted.

## Community and engagement (Phase 6)

- **Who sees what**: the teacher community is open to teachers and admins of every school and closed to students. Each student community belongs to one school. Its teachers and admin can read and report there, but only students post, comment and vote.
- **Voting**: one vote per person per post (changing or removing it is allowed). You can't vote on your own post. Teachers and admins don't vote in the student community.
- **Saving and replies**: anyone who can read a post can save it ("Saved" filter). Comments take one level of replies. Authors can delete their own posts and comments.
- **Reports and moderation**: anyone who can read a post or comment can report it (reason plus optional details, once each). The admin of the school that owns the content reviews reports under **Moderation**. That is the post's school in the student community, or the author's school in the teacher community. The admin can hide content (with a note to the author), restore it, or keep it visible. Content reported by three different people is hidden automatically until reviewed. Hidden content stays in the database and is visible only to its author and the moderator. Moderation actions go to the audit log.
- **Safety and rate limits**: student posts and comments can't contain links, email addresses or phone numbers. No space accepts `javascript:` or `data:` links. Per user: 5 posts per 10 minutes, 20 comments per 10 minutes, 60 votes per minute, 10 reports per hour (in-process limiter, see Deployment notes).
- **Notifications** (bell in the navigation, `/notifications`): new assignments and exams, published memos, replies to your posts and comments, moderation of your content, and new reports for admins. Votes don't notify anyone.
- **XP ledger**: every XP change is a row in `student_xp_events` with its reason, so totals can be explained and recalculated. Students see their breakdown on the Profile page; everyone can see "How XP is earned" there.
- **School calendar** (`/calendar`): admins add school events (event, holiday, exam, meeting, deadline) for everyone, teachers only or students only. Terms come from the academic years. Students also see their assignment due dates and exam windows; teachers see their own assignments' due dates and published exams.

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
- admin user management: cross-school isolation, no admin creation or role escalation, validation and duplicate detection, invitations and admin-initiated resets without exposing passwords, disable/reactivate;
- CSV import preview and confirm; academic years and terms; class creation, enrolment, transfer, withdrawal and archiving, and the effect on teacher access;
- derived teacher responsibilities;
- forgot, reset and change password, the password policy, and token invalidation;
- audit logging, and the admin CLI;
- the AI flag;
- content status and memo visibility; one scored answer per quiz question;
- exam publishing scope (wrong subject/class, students outside the class), exam and assignment answer release, assignment windows;
- community isolation between schools and spaces, one vote per user, reports and moderation (including other-school admins), auto-hide, link/contact filtering, replies, bookmarks, rate limits, notifications, calendar audience and scope, and the XP ledger adding up;
- production settings checks, security headers and the database health check, upload type checks, memo attachment permissions, CSV escaping, the seed refusing hosted databases, and `load-curriculum` on an empty database;
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
3. `cd backend && alembic stamp 0001 && alembic upgrade head`, then run `supabase/migrations/0002_phase1_auth_rls.sql` and `0003_phase2_school_admin_rls.sql`.
4. Frontend `.env`: `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (the anon key only; never the service-role key).
5. Disable public sign-ups in Supabase Auth settings. Accounts that are created anyway become students (trigger `handle_new_user`). Grant admin with `python -m app.cli grant-admin`.

The demo seed refuses to run with `AUTH_MODE=supabase`, against a Supabase URL, or in production.

RLS files in `supabase/migrations` follow the Alembic revisions: `0003` after 0003, `0004` after 0004, `0005` (exams) after 0006, `0006` (community and engagement) after 0007.

> The Supabase path has not yet been verified against a live Supabase project; Phases 1 and 2 were verified with local PostgreSQL. In `AUTH_MODE=supabase`, creating accounts, importing and sending set-password links from the admin screens return `501`, because they need the Supabase Admin API on the server. Until that is added, create users in Supabase and manage their details here.

## Deployment notes

The full guide is [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). It covers environment variables, the first admin, starter content, email, file storage, the static frontend and post-deploy checks. In short:

- **Frontend**: `npm run build` produces a static `frontend/dist`. Set `VITE_API_URL` if the API isn't served from the same origin at `/api`.
- **Backend**: `alembic upgrade head`, then `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. With `ENVIRONMENT=production` the API refuses to start with a weak `APP_SECRET`, SQLite, `CORS_ORIGINS=*` or a localhost `FRONTEND_URL`, and `/docs` is turned off.
- **Email**: set `SMTP_*` so invitations and password-reset links are delivered.
- **First admin and content**: `python -m app.cli create-admin ... --school-name ...`, then optionally `python -m app.cli load-curriculum`.
- **Files**: `UPLOAD_DIR` (public question images) and `PRIVATE_UPLOAD_DIR` (memo attachments) must be on a persistent disk.
- **One process**: rate limits are in memory. Running several workers or instances needs a shared store first.

## Hardening (Phase 7)

- **Security headers**: the API sends `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store` on API responses. In production it also sends HSTS. Uploaded files get a sandboxing Content-Security-Policy.
- **Uploads**: a file's leading bytes must match its declared type, so a script renamed to `.png` is rejected. Memo attachments are private: the same audience rules as the memo decide who can download them. Admins can add up to five per memo and remove them.
- **CSV export**: the acknowledgement report is properly quoted, and cells that start with `=`, `+`, `-` or `@` are neutralised so they can't run as spreadsheet formulas.
- **Email**: an SMTP sender (`SMTP_*`). Emailed links are never written to logs outside development.
- **Health check**: `/api/health` pings the database and returns 503 if it is unreachable.
- **Seed safety**: the demo seed also refuses any database that isn't on this machine.
- **Honest labels**: generated practice questions show "Sample question · 2021 style" instead of "SPM 2021 · Paper 1", and recommendations only say "SPM" for questions marked as real past-year papers.
- **Phone layout**: the bottom bar shows four destinations plus **More** when a role has more pages.

## Roadmap

See [`docs/PLAN.md`](docs/PLAN.md). Phase 3 onward covers:

- subject and content management, file uploads (including a school logo upload; Phase 2 takes a logo URL), and school memos;
- the school calendar (Phase 6);
- homework and assessments, and announcements;
- reports and analytics;
- the moved-over learning features;
- the optional AI services.
