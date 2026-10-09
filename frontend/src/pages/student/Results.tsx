import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowRight, CheckCircle2, Flame, Home, RotateCcw, Star, Target, Trophy } from "lucide-react";
import { LEVEL_STYLE, MasteryBadge, levelFor } from "@/components/mastery";
import { ProgressRing } from "@/components/progress-ring";
import { FeedbackPanel, QuestionMeta } from "@/components/question-card";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { QuizResult, QuizSession } from "@/types";

export default function ResultsPage() {
  const { setId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [result, setResult] = useState<QuizResult | null>((location.state as QuizResult) ?? null);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (!result) api.get<QuizResult>(`/api/quiz/${setId}/results`).then(setResult).catch((e) => setError(e.message));
  }, [result, setId]);

  if (error) return <ErrorState message={error} />;
  if (!result) return <PageLoader rows={2} />;

  const wrong = result.wrong_questions ?? [];
  const hasMastery = result.mastery_after != null;
  const change = result.mastery_change ?? 0;
  const afterLevel = levelFor(result.mastery_after);
  const great = result.percentage >= 80;

  const tryAgain = async () => {
    setRetrying(true);
    try {
      const quiz = await api.post<QuizSession>("/api/quiz/start", { topic_id: result.topic.id });
      navigate(`/quiz/${quiz.id}`);
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="bg-hero relative overflow-hidden rounded-3xl p-6 text-center text-white shadow-xl sm:p-8">
        <p className="animate-pop text-5xl" aria-hidden>
          {great ? "🎉" : result.percentage >= 50 ? "💪" : "🌱"}
        </p>
        <h1 className="mt-2 text-2xl font-extrabold sm:text-3xl">{great ? "Topic Complete!" : result.percentage >= 50 ? "Nice effort!" : "Every attempt counts!"}</h1>
        <p className="text-white/85">{result.topic.name}</p>
        <div className="mt-6 flex flex-col items-center justify-center gap-6 sm:flex-row">
          <ProgressRing value={result.percentage} size={140} stroke={13}>
            <span className="text-3xl font-extrabold">
              {result.score} / {result.total}
            </span>
            <span className="text-sm font-semibold text-white/85">{Math.round(result.percentage)}%</span>
          </ProgressRing>
          {hasMastery && (
            <div className="rounded-2xl bg-white/15 p-4 backdrop-blur">
              <p className="text-xs font-bold uppercase tracking-wide text-white/75">Topic mastery</p>
              <p className="text-2xl font-extrabold">
                {Math.round(result.mastery_before)}% → {Math.round(result.mastery_after)}%
              </p>
              <p className="text-sm font-semibold">{change > 0 ? `You improved by +${Math.round(change)}%! 🚀` : change < 0 ? "Keep practising — you'll bounce back." : "Holding steady."}</p>
            </div>
          )}
        </div>
        {result.xp_gained != null && (
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 text-sm font-bold">
              <Star className="size-4" /> +{result.xp_gained} XP
            </span>
            {result.streak > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-orange-400/90 px-3 py-1.5 text-sm font-bold">
                <Flame className="size-4" /> {result.streak} day streak
              </span>
            )}
          </div>
        )}
      </section>

      {result.new_badges?.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {result.new_badges.map((b) => (
            <Card key={b.code} className="animate-pop flex-row items-center gap-4 border-amber-200 bg-gradient-to-r from-amber-50 to-pink-50">
              <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-300 to-pink-400 text-white shadow-md">
                <Trophy className="size-6" />
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-amber-700">🏆 New badge</p>
                <p className="font-extrabold">"{b.name}"</p>
                <p className="text-xs text-muted-foreground">{b.description}</p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {(result.strong_areas?.length > 0 || result.weak_areas?.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Card className="gap-2">
            <CardTitle className="text-base">Strong areas</CardTitle>
            {result.strong_areas.length ? (
              result.strong_areas.map((s) => (
                <p key={s} className="flex items-center gap-2 text-sm font-semibold text-emerald-700">
                  <CheckCircle2 className="size-4" /> {s}
                </p>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">Keep going — strengths will show up here.</p>
            )}
          </Card>
          <Card className="gap-2">
            <CardTitle className="text-base">Needs practice</CardTitle>
            {result.weak_areas.length ? (
              result.weak_areas.map((s) => (
                <p key={s} className="flex items-center gap-2 text-sm font-semibold text-orange-700">
                  <AlertTriangle className="size-4" /> {s}
                </p>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">Nothing — perfect score! 🌟</p>
            )}
          </Card>
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button variant="gradient" onClick={tryAgain} disabled={retrying}>
          {retrying ? <Spinner /> : <RotateCcw />} Try again
        </Button>
        <Button asChild variant="outline">
          <Link to={`/practice?subject=${result.topic.subject_id}&topic=${result.topic.id}`}>
            <Target /> Practice weak areas
          </Link>
        </Button>
        {result.next_topic && (
          <Button asChild variant="outline">
            <Link to={`/topics/${result.next_topic.id}`}>
              Next: {result.next_topic.name} <ArrowRight />
            </Link>
          </Button>
        )}
        <Button asChild variant="ghost">
          <Link to="/">
            <Home /> Dashboard
          </Link>
        </Button>
      </div>

      {result.next_topic && (
        <Card className="flex-row items-center gap-4">
          <div className={`flex size-11 items-center justify-center rounded-xl border ${LEVEL_STYLE[levelFor(result.next_topic.mastery, result.next_topic.mastery ? 1 : 0)].bg}`}>
            <ArrowRight className="size-5" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Recommended next topic</p>
            <p className="font-bold">{result.next_topic.name}</p>
            <p className="text-xs text-muted-foreground">
              {result.next_topic.reason} · current mastery {Math.round(result.next_topic.mastery)}%
            </p>
          </div>
          {hasMastery && <MasteryBadge level={afterLevel} className="hidden sm:inline-flex" />}
        </Card>
      )}

      {wrong.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-xl font-extrabold">Review your mistakes</h2>
          {wrong.map((w) => (
            <Card key={w.question.id} className="gap-3">
              <QuestionMeta q={w.question} />
              <p className="font-bold whitespace-pre-line">{w.question.question_text}</p>
              {w.attempt_id ? (
                <FeedbackPanel
                  questionId={w.question.id}
                  feedback={{
                    question_id: w.question.id,
                    attempt_id: w.attempt_id,
                    is_correct: false,
                    your_answer: w.your_answer ?? "",
                    your_answer_display: w.your_answer_display,
                    correct_answer: w.correct_answer ?? "",
                    correct_display: w.correct_display,
                    explanation: w.explanation ?? null,
                    xp_gained: 0,
                  }}
                />
              ) : (
                <p className="text-sm">
                  Not answered · Correct answer: <span className="font-semibold">{w.correct_display}</span>
                </p>
              )}
            </Card>
          ))}
        </section>
      )}
    </div>
  );
}
