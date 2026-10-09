-- MINDA Phase 2: RLS for academic years/terms and enrolment history.
--
-- Table/column changes come from Alembic (backend/migrations, revision 0003).
-- After `alembic upgrade head`, run this file in the Supabase SQL editor.
--
-- FastAPI remains the enforcement point; these policies are defence in depth
-- for any direct client access with the anon key. All Phase 2 writes go
-- through the backend, so no insert/update/delete policies are defined.

-- Teachers keep access only through active classes and active enrolments;
-- admins only within their own school.
create or replace function public.teacher_can_view(p_student uuid, p_subject uuid default null) returns boolean
language sql stable security definer set search_path = public as $$
  select
    (
      public.current_role_name() = 'admin'
      and exists (select 1 from public.profiles p where p.id = p_student and p.school_id = public.current_school_id())
    )
    or exists (
      select 1 from public.classes c
      join public.class_students cs on cs.class_id = c.id
      where c.class_teacher_id = auth.uid() and c.status = 'active'
        and cs.student_id = p_student and cs.status = 'active'
    )
    or exists (
      select 1 from public.teacher_subjects ts
      join public.classes c on c.id = ts.class_id
      join public.class_students cs on cs.class_id = ts.class_id
      where ts.teacher_id = auth.uid() and c.status = 'active'
        and cs.student_id = p_student and cs.status = 'active'
        and (p_subject is null or ts.subject_id = p_subject)
    )
$$;

drop policy if exists "teachers see their classes" on public.classes;
create policy "teachers see their classes" on public.classes for select to authenticated using (
  status = 'active' and (
    class_teacher_id = auth.uid()
    or exists (select 1 from public.teacher_subjects ts where ts.class_id = classes.id and ts.teacher_id = auth.uid())
  )
);

-- Students still see past classes (their own enrolment history).
-- "students see own class" from 0001 is unchanged.

alter table public.academic_years enable row level security;
alter table public.academic_terms enable row level security;

create policy "read own school academic years" on public.academic_years for select to authenticated using (
  school_id = public.current_school_id()
);
create policy "read own school academic terms" on public.academic_terms for select to authenticated using (
  exists (
    select 1 from public.academic_years y
    where y.id = academic_terms.academic_year_id and y.school_id = public.current_school_id()
  )
);
