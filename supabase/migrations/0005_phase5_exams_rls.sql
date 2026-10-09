-- MINDA Phase 5: read policies for published exams and attempts.
-- Run after Alembic revision 0006. Writes, marking and answer release stay on the backend.

alter table public.exam_publications enable row level security;
alter table public.exam_attempts enable row level security;
alter table public.exam_answers enable row level security;

create policy "read class exam publications" on public.exam_publications for select to authenticated using (
  published_by = auth.uid()
  or exists (
    select 1 from public.class_students cs
    where cs.class_id = exam_publications.class_id and cs.student_id = auth.uid() and cs.status = 'active'
  )
);
create policy "read own exam attempts" on public.exam_attempts for select to authenticated using (
  student_id = auth.uid()
  or exists (select 1 from public.exam_publications p where p.id = exam_attempts.publication_id and p.published_by = auth.uid())
);
-- exam_answers carries is_correct, so students only see their rows once answers are released.
create policy "read own released exam answers" on public.exam_answers for select to authenticated using (
  exists (
    select 1 from public.exam_attempts a join public.exam_publications p on p.id = a.publication_id
    where a.id = exam_answers.attempt_id
      and ((a.student_id = auth.uid() and a.submitted_at is not null and p.release_at <= now()) or p.published_by = auth.uid())
  )
);
