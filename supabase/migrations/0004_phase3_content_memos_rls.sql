-- MINDA Phase 3: read policies for content status and school memos.
-- Run after Alembic revision 0004. Writes stay on the backend.

alter table public.subject_form_levels enable row level security;
alter table public.learning_objectives enable row level security;
alter table public.topic_prerequisites enable row level security;
alter table public.school_memos enable row level security;
alter table public.memo_attachments enable row level security;
alter table public.memo_reads enable row level security;
alter table public.memo_acknowledgements enable row level security;

drop policy if exists "read subjects" on public.subjects;
drop policy if exists "read topics" on public.topics;
drop policy if exists "read lessons" on public.lessons;
create policy "read published subjects" on public.subjects for select to authenticated using (status = 'published');
create policy "read published topics" on public.topics for select to authenticated using (status = 'published');
create policy "read published lessons" on public.lessons for select to authenticated using (status = 'published');
create policy "read form levels" on public.subject_form_levels for select to authenticated using (true);
create policy "read objectives" on public.learning_objectives for select to authenticated using (
  exists (select 1 from public.topics t where t.id = learning_objectives.topic_id and t.status = 'published')
);
create policy "read prerequisites" on public.topic_prerequisites for select to authenticated using (
  exists (select 1 from public.topics t where t.id = topic_prerequisites.topic_id and t.status = 'published')
);

create policy "read live memos" on public.school_memos for select to authenticated using (
  school_id = public.current_school_id() and status = 'published'
  and (publish_at is null or publish_at <= now())
  and (expires_at is null or expires_at > now())
);
create policy "read memo attachments" on public.memo_attachments for select to authenticated using (
  exists (select 1 from public.school_memos m where m.id = memo_attachments.memo_id and m.school_id = public.current_school_id())
);
create policy "own memo reads" on public.memo_reads for select to authenticated using (user_id = auth.uid());
create policy "own memo acknowledgements" on public.memo_acknowledgements for select to authenticated using (user_id = auth.uid());
