import { useEffect, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, Flag, X } from "lucide-react";
import { QuestionCard } from "@/components/question-card";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";
import type { AnswerFeedback, QuizResult, QuizSession } from "@/types";

export default function QuizPage() {
  const { setId } = useParams();
  const navigate = useNavigate();
  const { data: quiz, error, loading, reload, setData } = useApi<QuizSession>(`/api/quiz/${setId}`);
  const [index, setIndex] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [startedAt, setStartedAt] = useState(Date.now());

  useEffect(() => {
    if (quiz) {
      const firstOpen = quiz.questions.findIndex((q) => !quiz.answers[q.id]);
      setIndex(firstOpen === -1 ? quiz.questions.length - 1 : firstOpen);
    }
    // only on first load
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quiz?.id]);

  useEffect(() => setStartedAt(Date.now()), [index]);

  if (loading && !quiz) return <div className="p-6"><PageLoader rows={1} /></div>;
  if (error || !quiz) return <div className="p-6"><ErrorState message={error ?? "Quiz not found"} onRetry={reload} /></div>;
  if (quiz.status === "completed") return <Navigate to={`/quiz/${quiz.id}/results`} replace />;

  const total = quiz.questions.length;
  const question = quiz.questions[index];
  const feedback = quiz.answers[question.id];
  const answered = Object.keys(quiz.answers).length;
  const isLast = index === total - 1;

  const answer = async (value: string) => {
    const fb = await api.post<AnswerFeedback>(`/api/quiz/${quiz.id}/answer`, {
      question_id: question.id,
      answer: value,
      time_spent_sec: Math.round((Date.now() - startedAt) / 1000),
    });
    setData({ ...quiz, answers: { ...quiz.answers, [question.id]: fb } });
  };

  const finish = async () => {
    setSubmitting(true);
    try {
      const result = await api.post<QuizResult>("/api/quiz/submit", { set_id: quiz.id });
      navigate(`/quiz/${quiz.id}/results`, { state: result, replace: true });
    } finally {
      setSubmitting(false);
    }
  };

  const nextOpen = () => {
    const after = quiz.questions.findIndex((q, i) => i > index && !quiz.answers[q.id]);
    const any = quiz.questions.findIndex((q) => !quiz.answers[q.id]);
    setIndex(after !== -1 ? after : any !== -1 ? any : index);
  };

  const allDone = answered === total;

  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <header className="sticky top-0 z-10 border-b bg-card/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate(`/topics/${quiz.topic.id}`)} aria-label="Exit quiz">
            <X />
          </Button>
          <div className="flex-1 space-y-1.5">
            <div className="flex justify-between text-xs font-semibold text-muted-foreground">
              <span className="truncate">{quiz.topic.name}</span>
              <span>
                {answered} / {total} answered
              </span>
            </div>
            <Progress value={(answered / total) * 100} />
          </div>
        </div>
        <div className="mx-auto mt-3 flex max-w-2xl justify-center gap-1.5" role="tablist" aria-label="Questions">
          {quiz.questions.map((q, i) => {
            const fb = quiz.answers[q.id];
            return (
              <button
                key={q.id}
                onClick={() => setIndex(i)}
                aria-label={`Question ${i + 1}${fb ? (fb.is_correct ? ", correct" : ", incorrect") : ""}`}
                className={cn(
                  "flex size-7 items-center justify-center rounded-lg text-xs font-bold transition-all",
                  i === index && "ring-2 ring-primary ring-offset-2",
                  !fb && "bg-muted text-muted-foreground",
                  fb?.is_correct && "bg-emerald-500 text-white",
                  fb && !fb.is_correct && "bg-orange-400 text-white",
                )}
              >
                {fb ? (fb.is_correct ? "✓" : "✗") : i + 1}
              </button>
            );
          })}
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-8">
        <QuestionCard key={question.id} question={question} feedback={feedback} onSubmit={answer} label={`Question ${index + 1} / ${total}`} />
      </main>

      <footer className="sticky bottom-0 border-t bg-card/95 px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur">
        <div className="mx-auto flex max-w-2xl justify-end gap-2">
          {allDone || (isLast && feedback) ? (
            <Button variant="gradient" size="lg" onClick={finish} disabled={submitting}>
              {submitting ? <Spinner /> : <Flag />} {allDone ? "See my results" : "Finish quiz"}
            </Button>
          ) : (
            feedback && (
              <Button variant="gradient" size="lg" onClick={nextOpen}>
                Next question <ArrowRight />
              </Button>
            )
          )}
        </div>
      </footer>
    </div>
  );
}
