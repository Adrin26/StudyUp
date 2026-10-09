import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Flame, Star, XCircle } from "lucide-react";
import { LEVEL_STYLE, MasteryBadge, MasteryBar } from "@/components/mastery";
import { ProgressRing } from "@/components/progress-ring";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Card, CardTitle } from "@/components/ui/card";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";
import type { StudentDetail } from "@/types";

export default function TeacherStudentPage() {
  const { studentId } = useParams();
  const [params] = useSearchParams();
  const subjectId = params.get("subject_id");
  const { data, error, loading, reload } = useApi<StudentDetail>(`/api/teachers/students/${studentId}${subjectId ? `?subject_id=${subjectId}` : ""}`);

  if (loading && !data) return <PageLoader rows={2} />;
  if (error || !data) return <ErrorState message={error ?? "Not found"} onRetry={reload} />;
  const style = LEVEL_STYLE[data.level.key];

  return (
    <div className="space-y-5">
      <Link to="/teacher" className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Dashboard
      </Link>

      <Card className="items-center gap-6 sm:flex-row">
        <ProgressRing value={data.overall ?? 0} size={120} stroke={11} color={style.hex} track="#eef0f5">
          <span className={`text-2xl font-extrabold ${style.text}`}>{data.overall != null ? `${Math.round(data.overall)}%` : "—"}</span>
          <span className="text-xs text-muted-foreground">overall</span>
        </ProgressRing>
        <div className="flex-1 space-y-2 text-center sm:text-left">
          <h1 className="text-2xl font-extrabold">{data.student.name}</h1>
          <p className="text-sm text-muted-foreground">{subjectId && data.subjects[0] ? `Overall ${data.subjects[0].name}` : "Across subjects you can view"}</p>
          <div className="flex flex-wrap justify-center gap-2 sm:justify-start">
            <MasteryBadge level={data.level.key} />
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold">
              <Star className="size-3.5" /> {data.student.xp.toLocaleString()} XP
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-semibold">
              <Flame className="size-3.5" /> {data.student.streak} day streak
            </span>
          </div>
        </div>
      </Card>

      {data.subjects.length === 0 && <EmptyState emoji="📭" title="No activity yet" description="This student hasn't attempted any questions in your subjects." />}

      <div className="grid gap-4 lg:grid-cols-2">
        {data.subjects.map((s) => (
          <Card key={s.id}>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">{s.name}</CardTitle>
              <span className="text-sm font-extrabold">{s.average != null ? `${Math.round(s.average)}%` : "—"}</span>
            </div>
            <p className="text-xs font-bold uppercase text-muted-foreground">Weakest topics first</p>
            <div className="space-y-3">
              {s.topics.map((t) => {
                const ts = LEVEL_STYLE[t.level.key];
                const Icon = ts.icon;
                return (
                  <div key={t.id} className="space-y-1">
                    <div className="flex items-center gap-2 text-sm">
                      <Icon className={`size-4 ${ts.text}`} aria-label={ts.label} />
                      <span className="flex-1 font-semibold">{t.name}</span>
                      <span className={`font-extrabold tabular-nums ${ts.text}`}>{Math.round(t.mastery)}%</span>
                    </div>
                    <MasteryBar value={t.mastery} level={t.level.key} />
                  </div>
                );
              })}
            </div>
          </Card>
        ))}
      </div>

      {data.recent_attempts.length > 0 && (
        <Card>
          <CardTitle className="text-base">Recent attempts</CardTitle>
          <div className="divide-y">
            {data.recent_attempts.map((a) => (
              <div key={a.id} className="flex items-center gap-3 py-2 text-sm">
                {a.is_correct ? <CheckCircle2 className="size-4 text-emerald-500" aria-label="Correct" /> : <XCircle className="size-4 text-orange-500" aria-label="Incorrect" />}
                <span className="flex-1 font-medium">{a.topic}</span>
                <span className="text-xs capitalize text-muted-foreground">
                  {a.difficulty} · {a.context}
                </span>
                <span className="w-24 text-right text-xs text-muted-foreground">{timeAgo(a.created_at)}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
