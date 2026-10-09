import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, EyeOff, Printer, Send, Trash2 } from "lucide-react";
import { AssignDialog } from "@/components/assign-dialog";
import { QuestionMeta } from "@/components/question-card";
import { ErrorState, PageLoader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { QuestionFull, SubjectDashboard } from "@/types";
import { ExamPublications } from "./ExamPublications";

interface Exam {
  id: string;
  title: string;
  subject_id: string;
  total_marks: number;
  created_at: string;
  questions: QuestionFull[];
}

export default function ExamDetailPage() {
  const { examId } = useParams();
  const navigate = useNavigate();
  const { data: exam, error, loading, reload } = useApi<Exam>(`/api/exams/${examId}`);
  const { data: roster } = useApi<SubjectDashboard>(exam ? `/api/teachers/subjects/${exam.subject_id}/progress` : null);
  const [showAnswers, setShowAnswers] = useState(false);

  if (loading && !exam) return <PageLoader rows={2} />;
  if (error || !exam) return <ErrorState message={error ?? "Exam not found"} onRetry={reload} />;

  const remove = async () => {
    if (!confirm("Delete this exam?")) return;
    try {
      await api.del(`/api/exams/${exam.id}`);
      navigate("/teacher/exams");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Could not delete this exam");
    }
  };

  return (
    <div className="space-y-5">
      <Link to="/teacher/exams" className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground print:hidden">
        <ArrowLeft className="size-4" /> Exams
      </Link>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">{exam.title}</h1>
          <p className="text-muted-foreground">
            {exam.questions.length} questions · {exam.total_marks} marks
          </p>
        </div>
        <div className="flex flex-wrap gap-2 print:hidden">
          <Button variant="outline" onClick={() => setShowAnswers(!showAnswers)}>
            {showAnswers ? <EyeOff /> : <Eye />} Answers
          </Button>
          <Button variant="outline" onClick={() => window.print()}>
            <Printer /> Print
          </Button>
          {roster && roster.students.length > 0 && (
            <AssignDialog
              subjectId={exam.subject_id}
              examId={exam.id}
              topicName={exam.title}
              students={roster.students.map((s) => ({ id: s.id, name: s.name }))}
              trigger={
                <Button variant="gradient">
                  <Send /> Assign
                </Button>
              }
            />
          )}
          <Button variant="ghost" onClick={remove} aria-label="Delete exam">
            <Trash2 />
          </Button>
        </div>
      </div>

      <ExamPublications examId={exam.id} />

      <ol className="space-y-3">
        {exam.questions.map((q, i) => (
          <Card key={q.id} className="gap-2 p-4 print:break-inside-avoid print:border-0 print:shadow-none">
            <div className="flex items-start gap-3">
              <span className="font-extrabold">{i + 1}.</span>
              <div className="flex-1 space-y-2">
                <div className="print:hidden">
                  <QuestionMeta q={q} />
                </div>
                <p className="font-semibold whitespace-pre-line">{q.question_text}</p>
                {q.options && (
                  <div className="grid gap-1 text-sm sm:grid-cols-2">
                    {q.options.map((o) => (
                      <p key={o.key} className={showAnswers && o.key === q.correct_answer ? "font-bold text-emerald-700" : ""}>
                        {o.key}. {o.text}
                      </p>
                    ))}
                  </div>
                )}
                {showAnswers && <p className="text-sm text-emerald-800">Answer: {q.correct_display}</p>}
              </div>
              <span className="shrink-0 text-xs font-semibold text-muted-foreground">[{q.marks}]</span>
            </div>
          </Card>
        ))}
      </ol>
    </div>
  );
}
