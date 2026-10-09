import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Bot, Flag, X } from "lucide-react";
import { AIAssistant } from "@/components/ai-assistant";
import { SlideView } from "@/components/slide-view";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { LessonData, QuizSession } from "@/types";

export default function LessonPage() {
  const { topicId } = useParams();
  const navigate = useNavigate();
  const { data: lesson, error, loading, reload } = useApi<LessonData>(`/api/lessons/topic/${topicId}`);
  const [index, setIndex] = useState(0);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    if (lesson) setIndex(lesson.completed ? 0 : Math.min(lesson.current_slide, lesson.slides.length - 1));
  }, [lesson]);

  const go = useCallback(
    (next: number) => {
      if (!lesson) return;
      const clamped = Math.max(0, Math.min(lesson.slides.length - 1, next));
      setIndex(clamped);
      if (!lesson.completed) api.put(`/api/lessons/${lesson.id}/progress`, { current_slide: clamped }).catch(() => undefined);
    },
    [lesson],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      if (e.key === "ArrowRight") go(index + 1);
      if (e.key === "ArrowLeft") go(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, index]);

  if (loading && !lesson) return <div className="p-6"><PageLoader rows={1} /></div>;
  if (error || !lesson) return <div className="p-6"><ErrorState message={error ?? "Lesson not found"} onRetry={reload} /></div>;

  const slide = lesson.slides[index];
  const last = index === lesson.slides.length - 1;

  const finish = async () => {
    setFinishing(true);
    await api.put(`/api/lessons/${lesson.id}/progress`, { current_slide: index, completed: true }).catch(() => undefined);
    try {
      const quiz = await api.post<QuizSession>("/api/quiz/start", { topic_id: lesson.topic_id });
      navigate(`/quiz/${quiz.id}`);
    } catch {
      navigate(`/topics/${lesson.topic_id}`);
    }
  };

  return (
    <div className="flex h-dvh flex-col bg-background">
      <header className="flex items-center gap-3 border-b bg-card px-4 py-3">
        <Button variant="ghost" size="icon" onClick={() => navigate(`/topics/${lesson.topic_id}`)} aria-label="Exit lesson">
          <X />
        </Button>
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex justify-between text-xs font-semibold text-muted-foreground">
            <span className="truncate">{lesson.title}</span>
            <span>
              {index + 1} / {lesson.slides.length}
            </span>
          </div>
          <Progress value={((index + 1) / lesson.slides.length) * 100} />
        </div>
        <Button variant="secondary" size="sm" className="lg:hidden" onClick={() => setAssistantOpen(true)}>
          <Bot /> Ask AI
        </Button>
      </header>

      <div className="flex min-h-0 flex-1">
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-2xl px-5 py-8 sm:py-12">
            <SlideView slide={slide} />
          </div>
        </main>
        <aside className="hidden w-96 border-l bg-card lg:block">
          <AIAssistant topicId={lesson.topic_id} slideId={slide.id} slideTitle={slide.title} />
        </aside>
      </div>

      <footer className="flex items-center justify-between gap-3 border-t bg-card px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <Button variant="outline" onClick={() => go(index - 1)} disabled={index === 0}>
          <ArrowLeft /> Previous
        </Button>
        <div className="hidden gap-1.5 sm:flex" aria-hidden>
          {lesson.slides.map((s, i) => (
            <button key={s.id} onClick={() => go(i)} className={`h-2 rounded-full transition-all ${i === index ? "w-6 bg-primary" : i < index ? "w-2 bg-primary/40" : "w-2 bg-muted-foreground/20"}`} />
          ))}
        </div>
        {last ? (
          <Button variant="gradient" onClick={finish} disabled={finishing}>
            {finishing ? <Spinner /> : <Flag />} Start knowledge check
          </Button>
        ) : (
          <Button variant="gradient" onClick={() => go(index + 1)}>
            Next <ArrowRight />
          </Button>
        )}
      </footer>

      <Dialog open={assistantOpen} onOpenChange={setAssistantOpen}>
        <DialogContent className="flex h-[85vh] flex-col gap-0 overflow-hidden p-0">
          <DialogTitle className="sr-only">AI Study Coach</DialogTitle>
          <AIAssistant topicId={lesson.topic_id} slideId={slide.id} slideTitle={slide.title} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
