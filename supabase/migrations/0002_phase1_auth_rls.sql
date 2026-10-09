-- MINDA Phase 1: RLS and helper changes for the Supabase deployment.
--
-- Table/column changes come from Alembic (backend/migrations, revision 0002).
-- On a database created from 0001_schema.sql:
--   1. cd backend && alembic stamp 0001 && alembic upgrade head
--   2. run this file in the Supabase SQL editor
--
-- FastAPI remains the enforcement point; these policies are defence in depth
-- for any direct client access with the anon key.

-- Disabled accounts no longer satisfy any role- or school-based policy.
create or replace function public.current_role_name() returns text
language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid() and status = 'active'
$$;

create or replace function public.current_school_id() returns uuid
language sql stable security definer set search_path = public as $$
  select school_id from public.profiles where id = auth.uid() and status = 'active'
$$;

-- Usernames and IDs are assigned by an admin through the API; sign-ups stay students.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, full_name, role, status)
  values (new.id, lower(new.email), coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)), 'student', 'active');
  return new;
end $$;

-- Student emails must not be readable by other users of the school.
drop policy if exists "same school directory" on public.profiles;

alter table public.audit_logs enable row level security;
alter table public.local_credentials enable row level security;
alter table public.password_reset_tokens enable row level security;

-- Admins read their own school's audit trail; writes happen only through the backend (service role).
create policy "admins read school audit log" on public.audit_logs for select to authenticated using (
  public.current_role_name() = 'admin' and (school_id = public.current_school_id() or school_id is null)
);

-- local_credentials and password_reset_tokens are only used when AUTH_MODE=local.
-- With RLS enabled and no policies, clients can never read them.
