-- AI Study Coach — Supabase schema + Row Level Security
-- Mirrors backend/app/models.py. The FastAPI backend connects with a privileged
-- role and enforces the same rules in Python (app/services/access.py); these
-- policies protect the data if anything ever talks to Supabase directly.

create extension if not exists "pgcrypto";

-- ------------------------------------------------------------------ tables

create table public.schools (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  state text
);

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text unique not null,
  full_name text not null,
  role text not null default 'student' check (role in ('student', 'teacher', 'admin')),
  teacher_types jsonb not null default '[]'::jsonb,
  school_id uuid references public.schools (id),
  form int,
  avatar_url text,
  xp int not null default 0,
  current_streak int not null default 0,
  longest_streak int not null default 0,
  last_active_date date,
  created_at timestamptz not null default now()
);

create table public.classes (
  id uuid primary key default gen_random_uuid(),
  school_id uuid not null references public.schools (id),
  name text not null,
  form int not null,
  year int not null,
  class_teacher_id uuid references public.profiles (id)
);

create table public.class_students (
  class_id uuid references public.classes (id) on delete cascade,
  student_id uuid references public.profiles (id) on delete cascade,
  primary key (class_id, student_id)
);

create table public.subjects (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  name text not null,
  icon text not null default 'book',
  color text not null default 'violet',
  description text,
  sort_order int not null default 0
);

create table public.topics (
  id uuid primary key default gen_random_uuid(),
  subject_id uuid not null references public.subjects (id) on delete cascade,
  name text not null,
  form int,
  description text,
  sort_order int not null default 0
);
create index on public.topics (subject_id);

create table public.student_subjects (
  student_id uuid references public.profiles (id) on delete cascade,
  subject_id uuid references public.subjects (id) on delete cascade,
  primary key (student_id, subject_id)
);

create table public.teacher_subjects (
  id uuid primary key default gen_random_uuid(),
  teacher_id uuid not null references public.profiles (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  class_id uuid not null references public.classes (id) on delete cascade,
  unique (teacher_id, subject_id, class_id)
);

create table public.lessons (
  id uuid primary key default gen_random_uuid(),
  topic_id uuid not null references public.topics (id) on delete cascade,
  title text not null,
  summary text,
  estimated_minutes int not null default 5
);

create table public.lesson_slides (
  id uuid primary key default gen_random_uuid(),
  lesson_id uuid not null references public.lessons (id) on delete cascade,
  position int not null,
  slide_type text not null,
  title text not null,
  content jsonb not null default '{}'::jsonb
);

create table public.lesson_progress (
  student_id uuid references public.profiles (id) on delete cascade,
  lesson_id uuid references public.lessons (id) on delete cascade,
  current_slide int not null default 0,
  completed boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (student_id, lesson_id)
);

create table public.questions (
  id uuid primary key default gen_random_uuid(),
  subject_id uuid not null references public.subjects (id) on delete cascade,
  topic_id uuid not null references public.topics (id) on delete cascade,
  year int,
  paper text,
  question_number int,
  question_text text not null,
  question_type text not null default 'mcq' check (question_type in ('mcq', 'short_answer')),
  difficulty text not null default 'medium' check (difficulty in ('easy', 'medium', 'hard')),
  marks int not null default 1,
  options jsonb,
  correct_answer text not null,
  explanation text,
  image_url text,
  skill text,
  source text not null default 'sample',
  status text not null default 'published' check (status in ('published', 'pending_review', 'rejected')),
  created_by uuid references public.profiles (id),
  created_at timestamptz not null default now()
);
-- Composite index for Subject → Topic → Year → Difficulty filtering/randomisation.
create index questions_filter_idx on public.questions (subject_id, topic_id, year, difficulty) where status = 'published';

create table public.question_sets (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('quiz', 'practice', 'assignment', 'exam')),
  title text not null,
  owner_id uuid not null references public.profiles (id) on delete cascade,
  subject_id uuid references public.subjects (id),
  topic_id uuid references public.topics (id),
  config jsonb not null default '{}'::jsonb,
  seed int,
  total_marks int,
  status text not null default 'active',
  result jsonb,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);
create index on public.question_sets (owner_id, kind);

create table public.question_set_questions (
  set_id uuid references public.question_sets (id) on delete cascade,
  question_id uuid references public.questions (id) on delete cascade,
  position int not null,
  marks int,
  primary key (set_id, question_id)
);

create table public.question_attempts (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references public.profiles (id) on delete cascade,
  question_id uuid not null references public.questions (id) on delete cascade,
  topic_id uuid not null references public.topics (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  set_id uuid references public.question_sets (id) on delete set null,
  answer text not null,
  is_correct boolean not null,
  difficulty text not null,
  context text not null default 'quiz',
  time_spent_sec int,
  created_at timestamptz not null default now()
);
create index on public.question_attempts (student_id, topic_id, created_at);

create table public.student_topic_progress (
  student_id uuid references public.profiles (id) on delete cascade,
  topic_id uuid references public.topics (id) on delete cascade,
  subject_id uuid not null references public.subjects (id) on delete cascade,
  mastery real not null default 0,
  recent_score real not null default 0,
  historical_score real,
  attempts_count int not null default 0,
  correct_count int not null default 0,
  quizzes_completed int not null default 0,
  last_attempt_at timestamptz,
  primary key (student_id, topic_id)
);

create table public.assignments (
  id uuid primary key default gen_random_uuid(),
  teacher_id uuid not null references public.profiles (id) on delete cascade,
  title text not null,
  instructions text,
  subject_id uuid not null references public.subjects (id),
  topic_id uuid references public.topics (id),
  set_id uuid not null references public.question_sets (id) on delete cascade,
  due_date date,
  created_at timestamptz not null default now()
);

create table public.assignment_students (
  assignment_id uuid references public.assignments (id) on delete cascade,
  student_id uuid references public.profiles (id) on delete cascade,
  status text not null default 'assigned',
  score real,
  completed_at timestamptz,
  primary key (assignment_id, student_id)
);

create table public.posts (
  id uuid primary key default gen_random_uuid(),
  author_id uuid not null references public.profiles (id) on delete cascade,
  space text not null check (space in ('student', 'teacher')),
  school_id uuid references public.schools (id),
  subject_id uuid references public.subjects (id),
  topic_id uuid references public.topics (id),
  category text,
  title text not null,
  body text not null,
  score int not null default 0,
  comment_count int not null default 0,
  created_at timestamptz not null default now()
);
create index on public.posts (space, school_id, created_at desc);

create table public.comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.posts (id) on delete cascade,
  author_id uuid not null references public.profiles (id) on delete cascade,
  body text not null,
  created_at timestamptz not null default now()
);

create table public.post_votes (
  post_id uuid references public.posts (id) on delete cascade,
  user_id uuid references public.profiles (id) on delete cascade,
  value int not null default 1 check (value in (-1, 1)),
  primary key (post_id, user_id)
);

create table public.badges (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  name text not null,
  description text not null,
  icon text not null,
  xp_reward int not null default 0
);

create table public.student_badges (
  student_id uuid references public.profiles (id) on delete cascade,
  badge_id uuid references public.badges (id) on delete cascade,
  earned_at timestamptz not null default now(),
  primary key (student_id, badge_id)
);

create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  kind text not null,
  title text not null,
  body text,
  link text,
  read boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.ai_cache (
  key text primary key,
  kind text not null,
  response jsonb not null,
  hits int not null default 0,
  created_at timestamptz not null default now()
);

create table public.ai_interactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  kind text not null,
  question_id uuid references public.questions (id) on delete set null,
  topic_id uuid references public.topics (id) on delete set null,
  prompt text,
  response jsonb not null,
  cached boolean not null default false,
  source text not null default 'openai',
  helpful boolean,
  created_at timestamptz not null default now()
);

-- ------------------------------------------------------- helper functions
-- SECURITY DEFINER so policies can consult membership tables without recursion.

create or replace function public.current_role_name() returns text
language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid()
$$;

create or replace function public.current_school_id() returns uuid
language sql stable security definer set search_path = public as $$
  select school_id from public.profiles where id = auth.uid()
$$;

create or replace function public.is_teacher() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(public.current_role_name() in ('teacher', 'admin'), false)
$$;

-- Class teachers: all subjects for students in their classes.
-- Subject teachers: only the subject they teach, for the classes they teach.
create or replace function public.teacher_can_view(p_student uuid, p_subject uuid default null) returns boolean
language sql stable security definer set search_path = public as $$
  select
    public.current_role_name() = 'admin'
    or exists (
      select 1 from public.classes c
      join public.class_students cs on cs.class_id = c.id
      where c.class_teacher_id = auth.uid() and cs.student_id = p_student
    )
    or exists (
      select 1 from public.teacher_subjects ts
      join public.class_students cs on cs.class_id = ts.class_id
      where ts.teacher_id = auth.uid() and cs.student_id = p_student
        and (p_subject is null or ts.subject_id = p_subject)
    )
$$;

-- New auth users always start as students; roles are granted by an admin.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)));
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- --------------------------------------------------------------- enable RLS

do $$
declare t text;
begin
  foreach t in array array[
    'schools','profiles','classes','class_students','subjects','topics','student_subjects','teacher_subjects',
    'lessons','lesson_slides','lesson_progress','questions','question_sets','question_set_questions',
    'question_attempts','student_topic_progress','assignments','assignment_students','posts','comments',
    'post_votes','badges','student_badges','notifications','ai_cache','ai_interactions'
  ] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

-- ---------------------------------------------------------------- policies

-- Reference content: readable by any signed-in user.
create policy "read schools" on public.schools for select to authenticated using (true);
create policy "read subjects" on public.subjects for select to authenticated using (true);
create policy "read topics" on public.topics for select to authenticated using (true);
create policy "read lessons" on public.lessons for select to authenticated using (true);
create policy "read slides" on public.lesson_slides for select to authenticated using (true);
create policy "read badges" on public.badges for select to authenticated using (true);

-- Profiles
create policy "own profile" on public.profiles for select to authenticated using (id = auth.uid());
create policy "teachers see their students" on public.profiles for select to authenticated using (public.teacher_can_view(id));
create policy "same school directory" on public.profiles for select to authenticated using (school_id = public.current_school_id());
-- Profile edits (role, XP, streaks) are made by the backend only; no client update policy.

-- Classes & membership
create policy "teachers see their classes" on public.classes for select to authenticated using (
  class_teacher_id = auth.uid()
  or exists (select 1 from public.teacher_subjects ts where ts.class_id = classes.id and ts.teacher_id = auth.uid())
);
create policy "students see own class" on public.classes for select to authenticated using (
  exists (select 1 from public.class_students cs where cs.class_id = classes.id and cs.student_id = auth.uid())
);
create policy "class membership" on public.class_students for select to authenticated using (
  student_id = auth.uid() or public.teacher_can_view(student_id)
);
create policy "own enrolment" on public.student_subjects for select to authenticated using (
  student_id = auth.uid() or public.teacher_can_view(student_id, subject_id)
);
create policy "own teaching" on public.teacher_subjects for select to authenticated using (teacher_id = auth.uid());

-- Questions: answers must never reach students directly. Clients get the
-- answer-free view below; the full table is backend-only.
create policy "teachers read published questions" on public.questions for select to authenticated using (
  public.is_teacher() and status = 'published'
);
create view public.questions_public with (security_invoker = false) as
  select id, subject_id, topic_id, year, paper, question_number, question_text, question_type,
         difficulty, marks, options, image_url, skill
  from public.questions where status = 'published';
grant select on public.questions_public to authenticated;

-- Learning records: students read their own; teachers read students they may view.
-- Writes happen only through the backend so scores can't be forged.
create policy "read own progress" on public.student_topic_progress for select to authenticated using (
  student_id = auth.uid() or public.teacher_can_view(student_id, subject_id)
);
create policy "read own attempts" on public.question_attempts for select to authenticated using (
  student_id = auth.uid() or public.teacher_can_view(student_id, subject_id)
);
create policy "read own lesson progress" on public.lesson_progress for select to authenticated using (student_id = auth.uid());

-- Question sets
create policy "owner reads sets" on public.question_sets for select to authenticated using (owner_id = auth.uid());
create policy "assigned students read sets" on public.question_sets for select to authenticated using (
  exists (
    select 1 from public.assignments a join public.assignment_students s on s.assignment_id = a.id
    where a.set_id = question_sets.id and s.student_id = auth.uid()
  )
);
create policy "read set items" on public.question_set_questions for select to authenticated using (
  exists (select 1 from public.question_sets qs where qs.id = set_id)
);

-- Assignments
create policy "teacher owns assignments" on public.assignments for select to authenticated using (teacher_id = auth.uid());
create policy "student sees assignments" on public.assignments for select to authenticated using (
  exists (select 1 from public.assignment_students s where s.assignment_id = assignments.id and s.student_id = auth.uid())
);
create policy "assignment status" on public.assignment_students for select to authenticated using (
  student_id = auth.uid()
  or exists (select 1 from public.assignments a where a.id = assignment_id and a.teacher_id = auth.uid())
);

-- Community: student space is per school; teacher space is for all teachers.
create policy "read posts" on public.posts for select to authenticated using (
  (space = 'student' and school_id = public.current_school_id())
  or (space = 'teacher' and public.is_teacher())
);
create policy "create posts" on public.posts for insert to authenticated with check (
  author_id = auth.uid() and (
    (space = 'student' and public.current_role_name() = 'student' and school_id = public.current_school_id())
    or (space = 'teacher' and public.is_teacher())
  )
);
create policy "delete own posts" on public.posts for delete to authenticated using (author_id = auth.uid());

create policy "read comments" on public.comments for select to authenticated using (
  exists (select 1 from public.posts p where p.id = post_id)
);
create policy "create comments" on public.comments for insert to authenticated with check (
  author_id = auth.uid() and exists (
    select 1 from public.posts p where p.id = post_id and (
      (p.space = 'student' and public.current_role_name() = 'student')
      or (p.space = 'teacher' and public.is_teacher())
    )
  )
);

create policy "own votes" on public.post_votes for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid() and exists (select 1 from public.posts p where p.id = post_id));

-- Gamification & notifications
create policy "own badges" on public.student_badges for select to authenticated using (
  student_id = auth.uid() or public.teacher_can_view(student_id)
);
create policy "own notifications" on public.notifications for select to authenticated using (user_id = auth.uid());
create policy "mark notifications read" on public.notifications for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- AI: cache is backend-only (no policies). Users can read and rate their own interactions.
create policy "own ai interactions" on public.ai_interactions for select to authenticated using (user_id = auth.uid());
create policy "rate own ai interactions" on public.ai_interactions for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());
