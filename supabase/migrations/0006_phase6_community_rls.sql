-- MINDA Phase 6: read policies for moderation, bookmarks, reports, XP ledger and calendar.
-- Run after Alembic revision 0007. Writes and moderation stay on the backend.

alter table public.post_bookmarks enable row level security;
alter table public.content_reports enable row level security;
alter table public.student_xp_events enable row level security;
alter table public.calendar_events enable row level security;

-- Hidden posts and comments are readable only by their author.
drop policy if exists "read posts" on public.posts;
create policy "read visible posts" on public.posts for select to authenticated using (
  (status = 'visible' or author_id = auth.uid())
  and (
    (space = 'teacher' and public.current_role_name() in ('teacher', 'admin'))
    or (space = 'student' and school_id = public.current_school_id())
  )
);
drop policy if exists "read comments" on public.comments;
create policy "read visible comments" on public.comments for select to authenticated using (
  (status = 'visible' or author_id = auth.uid())
  and exists (select 1 from public.posts p where p.id = comments.post_id)
);

create policy "own bookmarks" on public.post_bookmarks for select to authenticated using (user_id = auth.uid());
create policy "own reports" on public.content_reports for select to authenticated using (reporter_id = auth.uid());
create policy "admin school reports" on public.content_reports for select to authenticated using (
  public.current_role_name() = 'admin' and school_id = public.current_school_id()
);
create policy "own xp events" on public.student_xp_events for select to authenticated using (student_id = auth.uid());
create policy "school calendar" on public.calendar_events for select to authenticated using (
  school_id = public.current_school_id()
  and (
    audience = 'all'
    or (audience = 'teachers' and public.current_role_name() in ('teacher', 'admin'))
    or (audience = 'students' and public.current_role_name() in ('student', 'admin'))
  )
);
