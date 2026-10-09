import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, BookOpen, ClipboardList, GraduationCap, Layers, School, Users } from "lucide-react";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminOverview } from "@/types";
import { actionLabel, formatWhen } from "./audit";

export default function AdminDashboard() {
  const { user } = useAuth();
  const { data, error, isPending, refetch } = useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<AdminOverview>("/api/admin/overview") });

  if (isPending) return <PageLoader />;
  if (error || !data) return <ErrorState message={error?.message ?? "Could not load"} onRetry={() => refetch()} />;
  const c = data.counts;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">School administration</h1>
        <p className="text-muted-foreground">{user?.school ?? "Your school"} at a glance.</p>
      </div>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" aria-label="Summary">
        <StatCard icon={GraduationCap} label="Active students" value={String(c.active_students)} />
        <StatCard icon={Users} label="Active teachers" value={String(c.active_teachers)} tone="emerald" />
        <StatCard icon={School} label="Classes" value={String(c.classes)} tone="sky" />
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
              <li key={a.message} className="rounded-lg bg-card px-3 py-2">
                {a.message}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent accounts</CardTitle>
            <CardDescription>Newest accounts in your school.</CardDescription>
          </CardHeader>
          {data.recent_accounts.length === 0 ? (
            <EmptyState emoji="🧑‍🎓" title="No accounts yet" />
          ) : (
            <ul className="divide-y">
              {data.recent_accounts.map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate font-semibold">{a.name}</p>
                    <p className="text-xs text-muted-foreground">{formatWhen(a.created_at)}</p>
                  </div>
                  <div className="flex gap-1.5">
                    <Badge variant="secondary" className="capitalize">{a.role}</Badge>
                    {a.status !== "active" && <Badge variant="danger" className="capitalize">{a.status}</Badge>}
                  </div>
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
