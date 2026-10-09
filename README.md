# StudyUp — AI Study Coach (SPM Learning Hub)

A learning platform for Malaysian secondary students (Form 1–5) preparing for SPM, with dashboards for class and subject teachers.

Students learn a topic through short interactive slides, take a 10-question quiz, and see their mastery move. They can also practise SPM-style past-year questions or randomized sets, ask an AI tutor for hints, and discuss in a school-scoped community. Teachers see which students and topics need attention, assign targeted practice in two clicks, and generate exams from the question bank.

> **About the question bank:** the seeded questions are *SPM-style samples* generated for this demo, tagged with years 2019–2024 for filtering. They are **not** real SPM past-year papers. Import licensed questions into the `questions` table for real use.

## Quick start (local, no external services)

Requirements: Python 3.11+, Node 20+.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
copy .env.example .env                             # optional; defaults work
.venv\Scripts\python -m app.seed                   # creates studyup.db with a demo school
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                                        # http://localhost:5173
```

Vite proxies `/api` to `http://127.0.0.1:8000`. API docs: http://127.0.0.1:8000/docs.

### Demo accounts (password `demo1234`)

| Account | Role |
| --- | --- |
| `aisyah@student.demo` | Student, Form 4 Bestari — has an active streak, weak Quadratic Equations, and a pending assignment |
| `farid@teacher.demo` | Class teacher of 4 Bestari + Mathematics / Add Maths subject teacher |
| `rohana@teacher.demo` | Class teacher of 4 Cemerlang + Biology / History subject teacher |
| `tan@teacher.demo` | Subject teacher only (Physics, Chemistry, English) |

Every student account is `<firstname>@student.demo` (e.g. `ali@`, `sarah@`).

### AI features

Set `OPENAI_API_KEY` in `backend/.env` to enable OpenAI. Without a key, every AI feature (lesson help, hints, mistake explanations, similar questions, study summaries, teaching suggestions) returns a deterministic fallback, so the app is fully usable offline.

### Tests

```powershell
cd backend
.venv\Scripts\python -m pytest -q
```

## Architecture

```
frontend/   React + TypeScript + Vite + Tailwind v4 + shadcn-style UI + Recharts
backend/    FastAPI + SQLAlchemy 2 + Pydantic
  app/routers/    HTTP endpoints (auth, subjects, lessons, quiz, practice, exams, teachers, community, ai)
  app/services/   all business logic — deterministic, unit-tested
  app/seed/       demo curriculum, lessons, question generators, simulated history
supabase/migrations/0001_schema.sql   Postgres schema + Row Level Security
```

### What is deterministic vs. AI

All grading, scoring, mastery, randomization, exam generation, recommendations and analytics run in Python (`backend/app/services`). The LLM is only used for language: explanations, hints, summaries and teaching suggestions.

- **Mastery** (`services/mastery.py`): `evidence × (0.7 × recent + 0.3 × historical)`. *Recent* is difficulty-weighted accuracy over the last 10 attempts (easy 1, medium 1.5, hard 2); *evidence* ramps from 0.5 to 1 over the first 10 attempts, so two lucky answers don't read as "Mastered". Levels: 0–39 Needs Attention, 40–59 Developing, 60–79 Good, 80–100 Mastered. Levels are always shown with an icon and a label as well as a colour.
- **Randomization** (`services/randomizer.py`): a seeded `random.Random` over an id-sorted pool, so a practice set or exam can be reproduced from its stored seed. Difficulty mixes use largest-remainder allocation.
- **Quiz selection** prefers questions the student hasn't answered correctly yet, then orders easy → hard.
- **Recommendations** (`services/recommendations.py`): rule-based (pending assignment → weak topics → unfinished lesson → next topic → past-year practice). AI only writes the friendly summary.
- **Intervention alerts** (`services/analytics.py`): a topic is flagged when at least `max(3, class_size / 4)` students are below 50% mastery.
- **Gamification**: XP per answer (10/15/20 by difficulty; 2 for a wrong answer), quiz, perfect-quiz and lesson bonuses, levels every 500 XP, streaks counted in Malaysia time (UTC+8), and badges.

### AI safety and cost controls (`services/openai_service.py`)

- The OpenAI key lives only on the backend; React never calls OpenAI.
- Structured outputs (Pydantic schemas) with `max_completion_tokens` limits and a low-cost model (`gpt-4o-mini` by default).
- Responses are cached by a hash of the prompt payload (`ai_cache`), and each user has a daily request limit.
- Hints for an active question are checked by `answer_leaks()`; if the model reveals the answer, the hint is replaced by a safe fallback. Answers are never sent to the client before the student submits.
- AI-generated "similar questions" are validated (options, answer key) and stored as `pending_review`. They never enter the published bank automatically.
- Every call is logged in `ai_interactions`, with the 👍/👎 "Was this helpful?" feedback.

### Authorization

The backend checks every request, independent of the UI (`services/access.py`):

- Students only read and write their own progress.
- A **class teacher** sees every subject for students in their homeroom class.
- A **subject teacher** sees only their subject, and only for the classes they teach.
- The student community is scoped to the student's school (teachers can read it but not post). The teacher community spans schools.

On Supabase, the same rules are enforced again with RLS (`supabase/migrations/0001_schema.sql`), using `SECURITY DEFINER` helpers such as `teacher_can_view(student, subject)`. Progress and attempt tables are writable only through the backend (service role), so students can't edit their own scores. Questions are exposed to clients through the `questions_public` view, which has no answer columns.

## Using Supabase

1. Create a Supabase project and run `supabase/migrations/0001_schema.sql` in the SQL editor (or `supabase db push`).
2. Backend `.env`:
   ```
   AUTH_MODE=supabase
   DATABASE_URL=postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
   SUPABASE_URL=https://<ref>.supabase.co
   SUPABASE_JWT_SECRET=<legacy JWT secret>   # or leave empty to verify via JWKS
   ```
3. Frontend `.env` (copy from `frontend/.env.example`): `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`. When these are set, the login page uses Supabase Auth instead of the demo accounts.
4. New sign-ups get a `profiles` row with role `student` (trigger `handle_new_user`). Promote teachers, and set `teacher_types`, `school_id`, class and subject assignments, using the SQL editor or an admin tool.

The demo seed (`python -m app.seed`) only runs with `AUTH_MODE=demo` against SQLite or a local Postgres (`DATABASE_URL=postgresql+psycopg://postgres:<password>@localhost:5432/studyup`), never against Supabase: it drops all tables and creates profiles without matching `auth.users` rows. Load curriculum and questions into Supabase separately.

## Deployment notes

- **Frontend**: `npm run build` produces a static `frontend/dist` (Vercel, Netlify, Cloudflare Pages). Set `VITE_API_URL` to the backend URL if it isn't served under the same origin at `/api`.
- **Backend**: any container host (Render, Railway, Fly.io): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `ENVIRONMENT=production`, a strong `APP_SECRET`, `CORS_ORIGINS` set to the frontend URL, and the Supabase and OpenAI variables.
- Tables are created on startup with SQLAlchemy `create_all` for local SQLite. On Supabase, the SQL migration is the source of truth.

## MVP scope

Included: auth with roles, the student dashboard, Subject → Topic → Lesson → 10-question quiz → results, mastery tracking, past-year and randomized practice, AI hints and explanations with feedback, gamification, the community, teacher subject and class dashboards, intervention alerts with one-click assignments, and the exam generator.

Postponed: PDF export of exams (Print is available instead), voice, RAG over textbooks, a teacher review queue for AI-generated questions, admin UI, and parent accounts.
