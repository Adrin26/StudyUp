import { Link } from "react-router-dom";
import { ClipboardList, Plus } from "lucide-react";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/useApi";

interface ExamRow {
  id: string;
  title: string;
  subject: string;
  total_marks: number;
  question_count: number;
  created_at: string;
}

export default function ExamsPage() {
  const { data, error, loading, reload } = useApi<ExamRow[]>("/api/exams");
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Exams</h1>
          <p className="text-muted-foreground">Generate exams from the shared question bank.</p>
        </div>
        <Button asChild variant="gradient">
          <Link to="/teacher/exams/new">
            <Plus /> Create exam
          </Link>
        </Button>
      </div>
      {loading && !data && <PageLoader rows={3} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && data.length === 0 && (
        <EmptyState
          emoji="📝"
          title="No exams yet"
          description="Pick topics, years and a difficulty mix — the question bank does the rest."
          action={
            <Button asChild>
              <Link to="/teacher/exams/new">Create your first exam</Link>
            </Button>
          }
        />
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {data?.map((e) => (
          <Link key={e.id} to={`/teacher/exams/${e.id}`}>
            <Card className="flex-row items-center gap-4 transition-all hover:border-primary/30 hover:shadow-md">
              <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-500 text-white">
                <ClipboardList className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-bold">{e.title}</p>
                <p className="text-xs text-muted-foreground">
                  {e.subject} · {e.question_count} questions · {e.total_marks} marks
                </p>
              </div>
              <span className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleDateString("en-MY")}</span>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
