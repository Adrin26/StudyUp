import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Flag, PartyPopper, Shuffle } from "lucide-react";
import { QuestionCard } from "@/components/question-card";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { cn } from "@/lib/utils";
import type { AnswerFeedback, PracticeSet } from "@/types";

interface Summary {
  score: number;
  answered: number;
  total: number;
  percentage: number;
  by_topic: { topic: string; correct: number; total: number }[];
}

export default function PracticeSessionPage() {
  const { setId } = useParams();
  const { data: set, error, loading, reload, setData } = useApi<PracticeSet>(`/api/practice/sets/${setId}`);
  const [index, setIndex] = useState(0);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [finishing, setFinishing] = useState(false);

  if (loading && !set) return <PageLoader rows={1} />;
  if (error || !set) return <ErrorState message={error ?? "Practice set not found"} onRetry={reload} />;
  if (set.questions.length === 0) return <EmptyState emoji="📭" title="This set is empty" />;

  const total = set.questions.length;
  const q = set.questions[index];
  const answered = Object.keys(set.answers).length;

  const answer = async (value: string) => {
    const fb = await api.post<AnswerFeedback>("/api/practice/answer", { set_id: set.id, question_id: q.id, answer: value });
    setData({ ...set, answers: { ...set.answers, [q.id]: fb } });
  };

  const finish = async () => {
    setFinishing(true);
    try {
      setSummary(await api.post<Summary>(`/api/practice/sets/${set.id}/complete`));
    } finally {
      setFinishing(false);
    }
  };

  if (summary) {
    return (
      <div className="mx-auto max-w-xl space-y-4">
        <Card className="items-center gap-3 text-center">
          <PartyPopper className="size-12 text-violet-500" />
          <h1 className="text-2xl font-extrabold">Practice complete!</h1>
          <p className="text-4xl font-extrabold">
            {summary.score} / {summary.total}
          </p>
          <p className="text-muted-foreground">{Math.round(summary.percentage)}% correct · Your topic mastery has been updated.</p>
        </Card>
        <Card className="gap-3">
          {summary.by_topic.map((t) => (
            <div key={t.topic} className="space-y-1">
              <div className="flex justify-between text-sm font-semibold">
                <span>{t.topic}</span>
                <span>
                  {t.correct}/{t.total}
                </span>
              </div>
              <Progress value={(t.correct / t.total) * 100} />
            </div>
          ))}
        </Card>
        <div className="flex flex-wrap justify-center gap-2">
          <Button asChild variant="gradient">
            <Link to="/practice">
              <Shuffle /> New practice set
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/">Back to dashboard</Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <Link to={set.assignment ? "/" : "/practice"} className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> {set.assignment ? "Dashboard" : "Practice"}
      </Link>
      <div className="space-y-2">
        <h1 className="text-xl font-extrabold">{set.assignment?.title ?? set.title}</h1>
        {set.assignment?.instructions && <p className="text-sm text-muted-foreground">{set.assignment.instructions}</p>}
        <div className="flex items-center gap-3">
          <Progress value={(answered / total) * 100} />
          <span className="shrink-0 text-xs font-semibold text-muted-foreground">
            {answered}/{total}
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {set.questions.map((qq, i) => {
            const fb = set.answers[qq.id];
            return (
              <button
                key={qq.id}
                onClick={() => setIndex(i)}
                aria-label={`Question ${i + 1}`}
                className={cn("size-7 rounded-lg text-xs font-bold", i === index && "ring-2 ring-primary ring-offset-1", !fb && "bg-muted", fb?.is_correct && "bg-emerald-500 text-white", fb && !fb.is_correct && "bg-orange-400 text-white")}
              >
                {i + 1}
              </button>
            );
          })}
        </div>
      </div>

      <Card className="p-5 sm:p-6">
        <QuestionCard key={q.id} question={q} feedback={set.answers[q.id]} onSubmit={answer} showMeta label={`Question ${index + 1} of ${total}`} />
      </Card>

      <div className="flex justify-between">
        <Button variant="outline" disabled={index === 0} onClick={() => setIndex(index - 1)}>
          <ArrowLeft /> Previous
        </Button>
        {index < total - 1 ? (
          <Button variant="gradient" onClick={() => setIndex(index + 1)}>
            Next <ArrowRight />
          </Button>
        ) : (
          <Button variant="gradient" onClick={finish} disabled={finishing || answered === 0}>
            {finishing ? <Spinner /> : <Flag />} Finish
          </Button>
        )}
      </div>
    </div>
  );
}
