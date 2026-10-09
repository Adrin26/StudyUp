import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, ClipboardList, Flag, XCircle } from "lucide-react";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, assetUrl } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";
import type { QuestionPublic } from "@/types";

interface ExamListItem {
  publication_id: string;
  title: string;
  subject: string | null;
  question_count: number;
  total_marks: number;
  opens_at: string;
  closes_at: string;
  release_at: string;
  duration_minutes: number | null;
  window: "upcoming" | "open" | "closed";
  status: "not_started" | "in_progress" | "submitted";
  released: boolean;
  marks_awarded: number | null;
}

type ExamQuestion = QuestionPublic & {
  your_answer: string | null;
  your_answer_display: string | null;
  is_correct?: boolean;
  marks_awarded?: number;
  correct_display?: string;
  explanation?: string | null;
};

interface ExamSitting {
  publication_id: string;
  title: string;
  total_marks: number;
  deadline: string;
  submitted_at: string | null;
  release_at: string;
  released: boolean;
  marks_awarded: number | null;
  questions: ExamQuestion[];
}

const fmt = (d: string) => new Date(d).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export default function ExamsPage() {
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi<ExamListItem[]>("/api/my-exams");
  const [starting, setStarting] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  if (loading && !data) return <PageLoader rows={2} />;
  if (error || !data) return <ErrorState message={error ?? "Could not load exams"} onRetry={reload} />;

  const start = async (id: string) => {
    setStarting(id);
    setStartError(null);
    try {
      await api.post(`/api/my-exams/${id}/start`);
      navigate(`/exams/${id}`);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "Could not start the exam");
    } finally {
      setStarting(null);
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Exams</h1>
        <p className="text-muted-foreground">Exams your teachers have published to your class.</p>
      </div>
      {startError && <p className="text-sm text-orange-700">{startError}</p>}
      {data.length === 0 ? (
        <EmptyState emoji="📝" title="No exams yet" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {data.map((e) => (
            <Card key={e.publication_id} className="gap-2">
              <div className="flex items-start gap-2">
                <ClipboardList className="mt-0.5 size-5 text-primary" />
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{e.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {e.subject} · {e.question_count} questions · {e.total_marks} marks
                    {e.duration_minutes ? ` · ${e.duration_minutes} min` : ""}
                  </p>
                </div>
                {e.released ? (
                  <Badge variant="success">
                    {e.marks_awarded} / {e.total_marks}
                  </Badge>
                ) : (
                  <Badge variant="muted">{e.status === "submitted" ? "Submitted" : e.window === "upcoming" ? "Upcoming" : e.window === "open" ? "Open" : "Closed"}</Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {fmt(e.opens_at)} – {fmt(e.closes_at)} · answers released {fmt(e.release_at)}
              </p>
              <div>
                {e.status === "not_started" && e.window === "open" && (
                  <Button size="sm" variant="gradient" onClick={() => start(e.publication_id)} disabled={starting === e.publication_id}>
                    {starting === e.publication_id && <Spinner />} Start exam
                  </Button>
                )}
                {e.status === "in_progress" && (
                  <Button size="sm" variant="gradient" asChild>
                    <Link to={`/exams/${e.publication_id}`}>Continue</Link>
                  </Button>
                )}
                {e.status === "submitted" && (
                  <Button size="sm" variant="outline" asChild>
                    <Link to={`/exams/${e.publication_id}`}>{e.released ? "View results" : "View answers"}</Link>
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function ExamSittingPage() {
  const { publicationId } = useParams();
  const { data: exam, error, loading, reload, setData } = useApi<ExamSitting>(`/api/my-exams/${publicationId}`);
  const [submitting, setSubmitting] = useState(false);

  if (loading && !exam) return <PageLoader rows={2} />;
  if (error || !exam) return <ErrorState message={error ?? "Exam not found"} onRetry={reload} />;

  const answered = exam.questions.filter((q) => q.your_answer != null).length;
  const locked = exam.submitted_at != null;

  const save = async (questionId: string, value: string) => {
    const res = await api.post<{ question_id: string; your_answer: string; your_answer_display: string }>(`/api/my-exams/${exam.publication_id}/answer`, {
      question_id: questionId,
      answer: value,
    });
    setData({ ...exam, questions: exam.questions.map((q) => (q.id === questionId ? { ...q, ...res } : q)) });
  };

  const submit = async () => {
    if (!confirm(`Submit the exam? You answered ${answered} of ${exam.questions.length} questions.`)) return;
    setSubmitting(true);
    try {
      setData(await api.post<ExamSitting>(`/api/my-exams/${exam.publication_id}/submit`));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Link to="/exams" className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Exams
      </Link>
      <div className="space-y-1">
        <h1 className="text-xl font-extrabold">{exam.title}</h1>
        {!locked && (
          <p className="text-sm text-muted-foreground">
            Ends {fmt(exam.deadline)} · {answered}/{exam.questions.length} answered · each saved answer is final
          </p>
        )}
        {locked && !exam.released && <p className="text-sm text-muted-foreground">Submitted. Your marks and the answers are released {fmt(exam.release_at)}.</p>}
        {exam.released && (
          <p className="text-lg font-extrabold">
            {exam.marks_awarded} / {exam.total_marks} marks
          </p>
        )}
      </div>

      <ol className="space-y-3">
        {exam.questions.map((q, i) => (
          <Card key={q.id} className="gap-3 p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold whitespace-pre-line">
                {i + 1}. {q.question_text}
              </p>
              <span className="shrink-0 text-xs font-semibold text-muted-foreground">[{q.marks}]</span>
            </div>
            {q.image_url && <img src={assetUrl(q.image_url)} alt="Question diagram" className="max-h-60 rounded-xl border" />}
            <ExamAnswer question={q} locked={locked} onSave={(v) => save(q.id, v)} />
            {exam.released && (
              <div className={cn("space-y-1 rounded-xl p-3 text-sm", q.is_correct ? "bg-emerald-50 text-emerald-900" : "bg-orange-50 text-orange-950")}>
                <p className="flex items-center gap-2 font-bold">
                  {q.is_correct ? <CheckCircle2 className="size-4" /> : <XCircle className="size-4" />}
                  {q.marks_awarded} / {q.marks} · Correct answer: {q.correct_display}
                </p>
                {q.explanation && <p className="whitespace-pre-line">{q.explanation}</p>}
              </div>
            )}
          </Card>
        ))}
      </ol>

      {!locked && (
        <Button variant="gradient" onClick={submit} disabled={submitting}>
          {submitting ? <Spinner /> : <Flag />} Submit exam
        </Button>
      )}
    </div>
  );
}

function ExamAnswer({ question, locked, onSave }: { question: ExamQuestion; locked: boolean; onSave: (value: string) => Promise<void> }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saved = question.your_answer;

  const save = async (v: string) => {
    if (!v.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSave(v.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save answer");
    } finally {
      setBusy(false);
    }
  };

  if (saved != null || locked) {
    return <p className="text-sm">Your answer: <span className="font-semibold">{question.your_answer_display ?? "Not answered"}</span></p>;
  }

  return (
    <div className="space-y-2">
      {question.question_type === "mcq" && question.options ? (
        <div className="grid gap-1.5 sm:grid-cols-2">
          {question.options.map((o) => (
            <button
              key={o.key}
              onClick={() => setValue(o.key)}
              disabled={busy}
              className={cn("rounded-xl border bg-card px-3 py-2 text-left text-sm font-semibold", value === o.key && "border-primary bg-primary/5")}
            >
              {o.key}. {o.text}
            </button>
          ))}
        </div>
      ) : (
        <Input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Type your answer" aria-label={`Answer`} />
      )}
      <Button size="sm" variant="outline" onClick={() => save(value)} disabled={!value.trim() || busy}>
        {busy && <Spinner />} Save answer
      </Button>
      {error && <p className="text-sm text-orange-700">{error}</p>}
    </div>
  );
}
