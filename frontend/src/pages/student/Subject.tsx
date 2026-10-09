import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ChevronRight, Target } from "lucide-react";
import { LEVEL_STYLE, MasteryBadge, MasteryBar } from "@/components/mastery";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { SubjectIcon } from "@/components/subject-style";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useApi } from "@/lib/useApi";
import type { SubjectSummary, TopicSummary } from "@/types";

export default function SubjectPage() {
  const { subjectId } = useParams();
  const { data, error, loading, reload } = useApi<{ subject: SubjectSummary; topics: TopicSummary[] }>(`/api/subjects/${subjectId}/topics`);

  if (loading && !data) return <PageLoader />;
  if (error || !data) return <ErrorState message={error ?? "Not found"} onRetry={reload} />;
  const { subject, topics } = data;

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Home
      </Link>

      <Card className="gap-5 sm:flex-row sm:items-center">
        <SubjectIcon icon={subject.icon} color={subject.color} size="lg" />
        <div className="flex-1 space-y-2">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight">{subject.name}</h1>
            <p className="text-sm text-muted-foreground">{subject.description}</p>
          </div>
          <div className="flex items-center gap-3">
            <Progress value={subject.progress} className="max-w-xs" />
            <span className="text-sm font-bold">Your progress: {Math.round(subject.progress)}%</span>
          </div>
        </div>
        <Button asChild variant="outline">
          <Link to={`/practice?subject=${subject.id}`}>
            <Target /> Practice questions
          </Link>
        </Button>
      </Card>

      <div className="flex flex-wrap gap-2" aria-label="Legend">
        {(["mastered", "good", "developing", "needs_attention", "not_started"] as const).map((k) => (
          <MasteryBadge key={k} level={k} />
        ))}
      </div>

      {topics.length === 0 ? (
        <EmptyState emoji="🧭" title="No topics yet" description="Your teachers are still preparing this subject." />
      ) : (
        <div className="space-y-3">
          <h2 className="text-lg font-extrabold">Topics</h2>
          {topics.map((t) => {
            const style = LEVEL_STYLE[t.level.key];
            const Icon = style.icon;
            return (
              <Link key={t.id} to={`/topics/${t.id}`} className="group block">
                <Card className="flex-row items-center gap-4 p-4 transition-all group-hover:border-primary/30 group-hover:shadow-md">
                  <div className={`flex size-11 shrink-0 items-center justify-center rounded-xl border ${style.bg} ${style.text}`}>
                    <Icon className="size-5" aria-hidden />
                  </div>
                  <div className="min-w-0 flex-1 space-y-1.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-bold">{t.name}</p>
                      <MasteryBadge level={t.level.key} className="hidden sm:inline-flex" />
                    </div>
                    <MasteryBar value={t.mastery} level={t.level.key} className="max-w-md" />
                    <p className="text-xs text-muted-foreground">
                      {t.question_count ? `${t.question_count} questions` : "Lesson only"}
                      {t.attempts > 0 && ` · ${t.attempts} answered`}
                    </p>
                  </div>
                  <span className={`text-lg font-extrabold tabular-nums ${style.text}`}>{t.attempts ? `${Math.round(t.mastery)}%` : "—"}</span>
                  <ChevronRight className="size-5 text-muted-foreground transition-transform group-hover:translate-x-1" />
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
