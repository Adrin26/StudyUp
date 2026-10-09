import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, BookOpen, CheckCircle2, Clock, History, ListChecks, PlayCircle, Target } from "lucide-react";
import { LEVEL_STYLE, MasteryBadge } from "@/components/mastery";
import { ProgressRing } from "@/components/progress-ring";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { SubjectIcon } from "@/components/subject-style";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { QuizSession, TopicSummary } from "@/types";

interface TopicDetail {
  topic: TopicSummary & { question_count: number };
  subject: { id: string; name: string; icon: string; color: string };
  lesson: { id: string; title: string; summary: string; estimated_minutes: number; slide_count: number; current_slide: number; completed: boolean } | null;
  quiz_history: { id: string; completed_at: string; percentage: number | null }[];
}

export default function TopicPage() {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useApi<TopicDetail>(`/api/topics/${topicId}`);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  if (loading && !data) return <PageLoader rows={2} />;
  if (error || !data) return <ErrorState message={error ?? "Not found"} onRetry={reload} />;
  const { topic, subject, lesson, quiz_history } = data;
  const style = LEVEL_STYLE[topic.level.key];

  const startQuiz = async () => {
    setStarting(true);
    setStartError(null);
    try {
      const quiz = await api.post<QuizSession>("/api/quiz/start", { topic_id: topic.id });
      navigate(`/quiz/${quiz.id}`);
    } catch (e) {
      setStartError(e instanceof Error ? e.message : "Could not start quiz");
      setStarting(false);
    }
  };

  const lessonStarted = lesson && (lesson.current_slide > 0 || lesson.completed);

  return (
    <div className="space-y-6">
      <Link to={`/subjects/${subject.id}`} className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> {subject.name}
      </Link>

      <Card className="items-center gap-6 sm:flex-row">
        <ProgressRing value={topic.mastery} size={128} stroke={12} color={style.hex} track="#eef0f5">
          <span className={`text-2xl font-extrabold ${style.text}`}>{topic.attempts ? `${Math.round(topic.mastery)}%` : "—"}</span>
          <span className="text-xs font-medium text-muted-foreground">mastery</span>
        </ProgressRing>
        <div className="flex-1 space-y-2 text-center sm:text-left">
          <div className="flex items-center justify-center gap-2 sm:justify-start">
            <SubjectIcon icon={subject.icon} color={subject.color} size="sm" />
            <span className="text-sm font-semibold text-muted-foreground">{subject.name}</span>
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{topic.name}</h1>
          <p className="text-muted-foreground">{topic.description}</p>
          <MasteryBadge level={topic.level.key} />
        </div>
      </Card>

      <div className="text-sm font-semibold text-muted-foreground">Learn → 10-question knowledge check → review → practice again</div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 to-indigo-500 text-white">
              <BookOpen className="size-5" />
            </div>
            <div>
              <CardTitle>Step 1 · Learn</CardTitle>
              <CardDescription>{lesson ? lesson.summary : "No lesson yet for this topic."}</CardDescription>
            </div>
          </div>
          {lesson && (
            <>
              <div className="flex items-center gap-4 text-xs font-semibold text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <Clock className="size-3.5" /> {lesson.estimated_minutes} min
                </span>
                <span>{lesson.slide_count} slides</span>
                {lesson.completed && (
                  <span className="inline-flex items-center gap-1 text-emerald-600">
                    <CheckCircle2 className="size-3.5" /> Completed
                  </span>
                )}
              </div>
              {!lesson.completed && lessonStarted && <Progress value={((lesson.current_slide + 1) / lesson.slide_count) * 100} />}
              <Button asChild variant={lesson.completed ? "outline" : "gradient"} className="mt-auto">
                <Link to={`/topics/${topic.id}/learn`}>
                  <PlayCircle /> {lesson.completed ? "Review lesson" : lessonStarted ? `Resume (slide ${lesson.current_slide + 1})` : "Start lesson"}
                </Link>
              </Button>
            </>
          )}
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white">
              <ListChecks className="size-5" />
            </div>
            <div>
              <CardTitle>Step 2 · Knowledge check</CardTitle>
              <CardDescription>
                {topic.question_count ? `${Math.min(10, topic.question_count)} questions · instant feedback · AI hints` : "Questions coming soon."}
              </CardDescription>
            </div>
          </div>
          {startError && <p className="text-sm text-orange-700">{startError}</p>}
          <Button onClick={startQuiz} disabled={starting || !topic.question_count} variant={lesson?.completed || !lesson ? "gradient" : "outline"} className="mt-auto">
            {starting ? <Spinner /> : <Target />} {topic.attempts ? "Practice again" : "Start quiz"}
          </Button>
        </Card>
      </div>

      {quiz_history.length > 0 && (
        <Card>
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="size-4" /> Recent quizzes
          </CardTitle>
          <div className="flex flex-wrap gap-2">
            {quiz_history.map((h) => (
              <Link key={h.id} to={`/quiz/${h.id}/results`} className="rounded-xl border px-3 py-2 text-sm hover:bg-muted">
                <span className="font-bold">{h.percentage != null ? `${Math.round(h.percentage)}%` : "—"}</span>
                <span className="ml-2 text-xs text-muted-foreground">{new Date(h.completed_at).toLocaleDateString("en-MY", { day: "numeric", month: "short" })}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
