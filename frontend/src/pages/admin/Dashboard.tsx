import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, BookOpen, ChevronRight, ClipboardList, FileUp, GraduationCap, Layers, School, UserPlus, Users } from "lucide-react";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminOverview } from "@/types";
import { actionLabel, formatWhen } from "./audit";
import { formatDate, ROLE_LABEL } from "./common";

const QUICK_ACTIONS = [
  { to: "/admin/users/new?role=student", label: "Add student", icon: UserPlus },
  { to: "/admin/users/new?role=teacher", label: "Add teacher", icon: UserPlus },
  { to: "/admin/users/import", label: "Import users", icon: FileUp },
  { to: "/admin/classes", label: "Classes & enrolment", icon: School },
  { to: "/admin/teacher-assignments", label: "Assign teachers", icon: Users },
];

function pct(part: number, whole: number) {
  return whole ? Math.round((part / whole) * 100) : 0;
}

export default function AdminDashboard() {
  const { user } = useAuth();
  const { data, error, isPending, refetch } = useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<AdminOverview>("/api/admin/overview") });

  if (isPending) return <PageLoader />;
  if (error || !data) return <ErrorState message={error?.message ?? "Could not load"} onRetry={() => refetch()} />;
  const c = data.counts;
  const year = data.current_academic_year;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">School administration</h1>
        <p className="text-muted-foreground">
          {user?.school ?? "Your school"}
          {year ? ` · Academic year ${year.name} (${formatDate(year.start_date)} – ${formatDate(year.end_date)})` : ""}
        </p>
      </div>

      <section className="flex flex-wrap gap-2" aria-label="Quick actions">
        {QUICK_ACTIONS.map((a) => (
          <Button key={a.to} variant="outline" size="sm" asChild>
            <Link to={a.to}>
              <a.icon /> {a.label}
            </Link>
          </Button>
        ))}
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Summary">
        <StatCard icon={GraduationCap} label="Active students" value={String(c.active_students)} />
        <StatCard icon={Users} label="Active teachers" value={String(c.active_teachers)} tone="emerald" />
        <StatCard icon={School} label="Active classes" value={String(c.classes)} tone="sky" />
        <StatCard icon={BookOpen} label="Subjects" value={String(c.subjects)} tone="violet" />
        <StatCard icon={Layers} label="Topics" value={String(c.topics)} tone="sky" />
        <StatCard icon={ClipboardList} label="Active assignments" value={String(c.active_assignments)} hint="Not yet past their due date" tone="orange" />
      </section>

      {data.alerts.length > 0 && (
        <Card className="gap-3 border-orange-200 bg-orange-50/60">
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="size-5 text-orange-500" /> Needs attention
          </CardTitle>
          <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
            {data.alerts.map((a) => (
              <li key={a.message}>
                {a.link ? (
                  <Link to={a.link} className="flex items-center justify-between gap-2 rounded-lg bg-card px-3 py-2 hover:bg-muted">
                    {a.message} <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
                  </Link>
                ) : (
                  <span className="block rounded-lg bg-card px-3 py-2">{a.message}</span>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Content completion</CardTitle>
          <CardDescription>How many topics in each subject have lesson material and practice questions.</CardDescription>
        </CardHeader>
        {data.content.length === 0 ? (
          <EmptyState emoji="📚" title="No subjects yet" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs font-semibold uppercase text-muted-foreground">
                <tr>
                  <th scope="col" className="py-2 pr-4">Subject</th>
                  <th scope="col" className="py-2 pr-4">Topics</th>
                  <th scope="col" className="py-2 pr-4">With lessons</th>
                  <th scope="col" className="py-2">With questions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {data.content.map((s) => (
                  <tr key={s.subject}>
                    <td className="py-2 pr-4 font-semibold">{s.subject}</td>
                    <td className="py-2 pr-4">{s.topics}</td>
                    <td className="py-2 pr-4">
                      {s.topics_with_lessons} <span className="text-muted-foreground">({pct(s.topics_with_lessons, s.topics)}%)</span>
                    </td>
                    <td className="py-2">
                      {s.topics_with_questions} <span className="text-muted-foreground">({pct(s.topics_with_questions, s.topics)}%)</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-start justify-between">
            <div className="space-y-1">
              <CardTitle>Recent accounts</CardTitle>
              <CardDescription>Newest accounts in your school.</CardDescription>
            </div>
            <Link to="/admin/users" className="text-sm font-semibold text-primary hover:underline">
              All users
            </Link>
          </CardHeader>
          {data.recent_accounts.length === 0 ? (
            <EmptyState emoji="🧑‍🎓" title="No accounts yet" />
          ) : (
            <ul className="divide-y">
              {data.recent_accounts.map((a) => (
                <li key={a.id}>
                  <Link to={`/admin/users/${a.id}`} className="flex items-center justify-between gap-3 py-2.5 hover:text-primary">
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{a.name}</p>
                      <p className="text-xs text-muted-foreground">{formatWhen(a.created_at)}</p>
                    </div>
                    <div className="flex gap-1.5">
                      <Badge variant="secondary">{ROLE_LABEL[a.role]}</Badge>
                      {a.status !== "active" && <Badge variant="danger" className="capitalize">{a.status}</Badge>}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between">
            <div className="space-y-1">
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>Account and administrative actions.</CardDescription>
            </div>
            <Link to="/admin/audit-log" className="text-sm font-semibold text-primary hover:underline">
              View all
            </Link>
          </CardHeader>
          {data.recent_activity.length === 0 ? (
            <EmptyState emoji="📜" title="No activity recorded yet" description="Account changes and administrative actions will appear here." />
          ) : (
            <ul className="divide-y">
              {data.recent_activity.map((e) => (
                <li key={e.id} className="py-2.5">
                  <p className="font-semibold">{actionLabel(e.action)}</p>
                  <p className="text-xs text-muted-foreground">
                    {e.actor ? e.actor.name : "System"} · {formatWhen(e.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
