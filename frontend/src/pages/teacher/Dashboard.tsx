import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Bot, BookOpenCheck, ClipboardList, Lightbulb, School, Send, Target, TrendingUp, Users } from "lucide-react";
import { AIFeedback } from "@/components/ai-feedback";
import { AssignDialog } from "@/components/assign-dialog";
import { LEVEL_STYLE, MasteryBadge, MasteryCell, levelFor } from "@/components/mastery";
import { StatCard } from "@/components/stat-card";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { SubjectIcon } from "@/components/subject-style";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { pct } from "@/lib/utils";
import type { AIResponse, Alert, ClassOverview, SubjectDashboard, TeacherContext } from "@/types";

type View = { kind: "class"; id: string; name: string } | { kind: "subject"; id: string; name: string };

export default function TeacherDashboard() {
  const { user } = useAuth();
  const { data: ctx, error, loading, reload } = useApi<TeacherContext>("/api/teachers/me");
  const [view, setView] = useState<View | null>(null);

  useEffect(() => {
    if (ctx && !view) {
      const c = ctx.homeroom_classes[0];
      const s = ctx.subjects[0];
      setView(c ? { kind: "class", id: c.id, name: c.name } : s ? { kind: "subject", id: s.id, name: s.name } : null);
    }
  }, [ctx, view]);

  if (loading && !ctx) return <PageLoader />;
  if (error || !ctx) return <ErrorState message={error ?? "Could not load"} onRetry={reload} />;

  const views: View[] = [
    ...ctx.homeroom_classes.map((c) => ({ kind: "class" as const, id: c.id, name: c.name })),
    ...ctx.subjects.map((s) => ({ kind: "subject" as const, id: s.id, name: s.name })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Welcome, {user?.full_name} 👋</h1>
          <p className="text-muted-foreground">Who needs your attention today?</p>
        </div>
        <div className="flex gap-1.5">
          {ctx.teacher_types.map((t) => (
            <Badge key={t} variant="secondary" className="capitalize">
              {t.replace("_", " ")}
            </Badge>
          ))}
        </div>
      </div>

      <Alerts />

      {views.length === 0 ? (
        <EmptyState emoji="🏫" title="No classes assigned yet" description="Ask your school admin to assign you to a class or subject." />
      ) : (
        <>
          <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1" role="tablist">
            {views.map((v) => {
              const active = view?.kind === v.kind && view.id === v.id;
              return (
                <button
                  key={`${v.kind}-${v.id}`}
                  role="tab"
                  aria-selected={active}
                  onClick={() => setView(v)}
                  className={`flex shrink-0 items-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold transition-all ${active ? "border-primary bg-primary text-primary-foreground shadow-md shadow-primary/25" : "bg-card hover:bg-muted"}`}
                >
                  {v.kind === "class" ? <School className="size-4" /> : <BookOpenCheck className="size-4" />}
                  {v.kind === "class" ? `Class ${v.name}` : v.name}
                </button>
              );
            })}
          </div>
          {view?.kind === "class" && <ClassView classId={view.id} />}
          {view?.kind === "subject" && <SubjectView subject={ctx.subjects.find((s) => s.id === view.id)!} />}
        </>
      )}

      <RecentAssignments />
    </div>
  );
}

function Alerts() {
  const { aiEnabled } = useAuth();
  const { data: alerts } = useApi<Alert[]>("/api/teachers/alerts");
  const [expanded, setExpanded] = useState<string | null>(null);
  if (!alerts || alerts.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="flex items-center gap-2 text-lg font-extrabold">
        <AlertTriangle className="size-5 text-orange-500" /> Attention required
      </h2>
      <div className="grid gap-3 lg:grid-cols-2">
        {alerts.slice(0, 4).map((a) => {
          const key = `${a.class_name}-${a.topic_id}`;
          return (
            <Card key={key} className="gap-3 border-orange-200 bg-gradient-to-br from-orange-50 to-amber-50/50">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-orange-800">
                    {a.struggling_count} students in {a.class_name} are struggling with:
                  </p>
                  <p className="text-lg font-extrabold">{a.topic}</p>
                  <p className="text-xs text-muted-foreground">{a.subject}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-extrabold text-orange-600">{Math.round(a.average)}%</p>
                  <p className="text-[11px] font-semibold text-muted-foreground">avg mastery</p>
                </div>
              </div>
              {expanded === key && (
                <div className="flex flex-wrap gap-1.5">
                  {a.students.map((s) => (
                    <Link key={s.id} to={`/teacher/students/${s.id}?subject_id=${a.subject_id}`} className="rounded-full border bg-card px-2.5 py-1 text-xs font-semibold hover:border-primary/40">
                      {s.name} · {Math.round(s.mastery)}%
                    </Link>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => setExpanded(expanded === key ? null : key)}>
                  <Users /> {expanded === key ? "Hide students" : "View students"}
                </Button>
                <AssignDialog
                  subjectId={a.subject_id}
                  topicId={a.topic_id}
                  topicName={a.topic}
                  students={a.students}
                  trigger={
                    <Button size="sm" variant="gradient">
                      <Send /> Assign practice
                    </Button>
                  }
                />
              </div>
              {aiEnabled && <TeachingIdeas alert={a} />}
            </Card>
          );
        })}
      </div>
    </section>
  );
}

function TeachingIdeas({ alert }: { alert: Alert }) {
  const [res, setRes] = useState<AIResponse<{ summary: string; likely_misconceptions: string[]; suggested_activities: string[] }> | null>(null);
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true);
    try {
      setRes(await api.post("/api/ai/teacher-suggestions", { topic_id: alert.topic_id, average: alert.average, struggling_count: alert.struggling_count }));
    } finally {
      setBusy(false);
    }
  };
  if (!res)
    return (
      <button onClick={load} disabled={busy} className="inline-flex w-fit items-center gap-1.5 text-xs font-semibold text-violet-700 hover:underline">
        {busy ? <Spinner className="size-3.5" /> : <Bot className="size-3.5" />} Suggest teaching ideas
      </button>
    );
  return (
    <div className="animate-pop space-y-2 rounded-xl border border-violet-200 bg-white/80 p-3 text-sm">
      <p className="font-semibold text-violet-900">{res.data.summary}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <p className="text-xs font-bold uppercase text-muted-foreground">Likely misconceptions</p>
          <ul className="list-disc pl-4">{res.data.likely_misconceptions.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
        <div>
          <p className="text-xs font-bold uppercase text-muted-foreground">Try this</p>
          <ul className="list-disc pl-4">{res.data.suggested_activities.map((m) => <li key={m}>{m}</li>)}</ul>
        </div>
      </div>
      <AIFeedback interactionId={res.interaction_id} />
    </div>
  );
}

function SubjectView({ subject }: { subject: TeacherContext["subjects"][number] }) {
  const navigate = useNavigate();
  const [classId, setClassId] = useState("");
  const { data, error, loading, reload } = useApi<SubjectDashboard>(`/api/teachers/subjects/${subject.id}/progress${classId ? `?class_id=${classId}` : ""}`);

  if (loading && !data) return <PageLoader rows={4} />;
  if (error || !data) return <ErrorState message={error ?? "Could not load"} onRetry={reload} />;

  const chart = data.topics.filter((t) => t.average != null).map((t) => ({ name: t.name, average: t.average }));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <SubjectIcon icon={data.subject.icon} color={data.subject.color} />
          <h2 className="text-xl font-extrabold">{data.subject.name} Dashboard</h2>
        </div>
        {subject.classes.length > 1 && (
          <Select value={classId} onChange={(e) => setClassId(e.target.value)} className="w-48" aria-label="Filter by class">
            <option value="">All my classes</option>
            {subject.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={TrendingUp} label="Class average" value={pct(data.class_average)} />
        <StatCard icon={Users} label="Students" value={String(data.student_count)} tone="sky" />
        <StatCard icon={AlertTriangle} label="Topics needing attention" value={String(data.topics_needing_attention)} tone="orange" />
        <StatCard icon={Target} label="Questions attempted" value={data.questions_attempted.toLocaleString()} tone="emerald" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Average mastery by topic</CardTitle>
            <CardDescription>Bars are coloured by mastery level.</CardDescription>
          </CardHeader>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ left: -20, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef0f5" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={50} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => [`${Number(v).toFixed(0)}%`, "Average"]} cursor={{ fill: "#f4f3ff" }} />
                <Bar dataKey="average" radius={[8, 8, 0, 0]}>
                  {chart.map((c) => (
                    <Cell key={c.name} fill={LEVEL_STYLE[levelFor(c.average)].hex} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardTitle className="text-base">Topics needing attention</CardTitle>
          <div className="space-y-2">
            {data.topics.filter((t) => t.needs_attention).length === 0 && <p className="text-sm text-muted-foreground">No topics flagged. 🎉</p>}
            {data.topics
              .filter((t) => t.needs_attention)
              .map((t) => (
                <div key={t.id} className="flex items-center gap-2 rounded-xl border border-orange-200 bg-orange-50/60 p-3">
                  <AlertTriangle className="size-4 shrink-0 text-orange-500" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold">{t.name}</p>
                    <p className="text-xs text-muted-foreground">{t.struggling_count} struggling</p>
                  </div>
                  <span className="text-sm font-extrabold text-orange-600">{pct(t.average)}</span>
                </div>
              ))}
          </div>
        </Card>
      </div>

      <Card className="gap-0 overflow-hidden p-0">
        <div className="border-b p-4">
          <CardTitle className="text-base">Students</CardTitle>
          <CardDescription>Click a student to see their weak topics and recent attempts.</CardDescription>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs font-bold text-muted-foreground uppercase">
              <tr>
                <th className="sticky left-0 bg-muted/50 px-4 py-3">Student</th>
                <th className="px-3 py-3">Overall</th>
                {data.topics.map((t) => (
                  <th key={t.id} className="px-3 py-3 whitespace-nowrap">
                    {t.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.students.map((s) => (
                <tr key={s.id} onClick={() => navigate(`/teacher/students/${s.id}?subject_id=${data.subject.id}`)} className="cursor-pointer border-t hover:bg-accent/40">
                  <td className="sticky left-0 bg-card px-4 py-2.5 font-semibold whitespace-nowrap">{s.name}</td>
                  <td className="px-3 py-2.5">
                    <MasteryCell value={s.overall} />
                  </td>
                  {data.topics.map((t) => (
                    <td key={t.id} className="px-3 py-2.5">
                      <MasteryCell value={s.topics[t.id]} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function ClassView({ classId }: { classId: string }) {
  const { data, error, loading, reload } = useApi<ClassOverview>(`/api/teachers/classes/${classId}/overview`);
  if (loading && !data) return <PageLoader rows={4} />;
  if (error || !data) return <ErrorState message={error ?? "Could not load"} onRetry={reload} />;

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-extrabold">Class {data.class.name}</h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={Users} label="Students" value={String(data.student_count)} tone="sky" />
        <StatCard icon={TrendingUp} label="Overall class performance" value={pct(data.class_average)} />
        <StatCard icon={AlertTriangle} label="Students needing attention" value={String(data.students_needing_attention.length)} tone="orange" />
        <StatCard icon={Lightbulb} label="Struggling topics" value={String(data.struggling_topics.filter((t) => t.average < 50).length)} tone="emerald" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardTitle className="text-base">Overall class performance by subject</CardTitle>
          <div className="space-y-2.5">
            {data.subjects.map((s) => {
              const level = levelFor(s.average);
              return (
                <div key={s.id} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 truncate text-sm font-semibold">{s.name}</span>
                  <div className="h-3 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className={`h-full rounded-full bg-gradient-to-r ${LEVEL_STYLE[level].bar}`} style={{ width: `${s.average}%` }} />
                  </div>
                  <span className={`w-12 text-right text-sm font-extrabold tabular-nums ${LEVEL_STYLE[level].text}`}>{Math.round(s.average)}%</span>
                </div>
              );
            })}
          </div>
        </Card>

        <Card>
          <CardTitle className="text-base">Top struggling topics</CardTitle>
          <ol className="space-y-2">
            {data.struggling_topics.map((t, i) => (
              <li key={t.id} className="flex items-center gap-3 rounded-xl border p-3">
                <span className="flex size-7 items-center justify-center rounded-lg bg-orange-100 text-sm font-extrabold text-orange-700">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold">{t.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {t.subject} · {t.struggling_count}/{t.students_attempted} struggling
                  </p>
                </div>
                <MasteryCell value={t.average} />
              </li>
            ))}
          </ol>
        </Card>
      </div>

      <Card>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertTriangle className="size-4 text-orange-500" /> Students needing attention
        </CardTitle>
        {data.students_needing_attention.length === 0 ? (
          <p className="text-sm text-muted-foreground">Everyone is on track. 🎉</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {data.students_needing_attention.map((s) => (
              <Link key={s.id} to={`/teacher/students/${s.id}`} className="rounded-2xl border p-4 transition-all hover:border-orange-300 hover:shadow-md">
                <div className="flex items-center justify-between">
                  <p className="font-bold">⚠ {s.name}</p>
                  <MasteryBadge level={levelFor(s.overall)} compact />
                </div>
                <p className="text-sm text-muted-foreground">Overall: {Math.round(s.overall)}%</p>
                {s.concerns.length > 0 && (
                  <div className="mt-2">
                    <p className="text-xs font-bold uppercase text-muted-foreground">Main concern</p>
                    {s.concerns.slice(0, 3).map((c) => (
                      <p key={c.subject} className="text-sm">
                        {c.subject} <span className="font-semibold text-orange-600">({Math.round(c.average)}%)</span>
                      </p>
                    ))}
                  </div>
                )}
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function RecentAssignments() {
  const { data } = useApi<{ id: string; title: string; subject: string; topic: string | null; assigned: number; completed: number; average_score: number | null; due_date: string | null }[]>("/api/teachers/assignments");
  if (!data || data.length === 0) return null;
  return (
    <Card>
      <CardTitle className="flex items-center gap-2 text-base">
        <ClipboardList className="size-4" /> Assignments
      </CardTitle>
      <div className="space-y-2">
        {data.slice(0, 5).map((a) => (
          <div key={a.id} className="flex items-center gap-3 rounded-xl border p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-bold">{a.title}</p>
              <p className="text-xs text-muted-foreground">
                {a.subject}
                {a.topic && ` · ${a.topic}`}
                {a.due_date && ` · due ${new Date(a.due_date).toLocaleDateString("en-MY", { day: "numeric", month: "short" })}`}
              </p>
            </div>
            <div className="text-right text-sm">
              <p className="font-bold">
                {a.completed}/{a.assigned} done
              </p>
              <p className="text-xs text-muted-foreground">{a.average_score != null ? `avg ${Math.round(a.average_score)}%` : "—"}</p>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
