import { useEffect, useState, type ReactNode } from "react";
import { Bot, CheckCircle2, Lightbulb, RefreshCw, Sparkles, XCircle } from "lucide-react";
import { AIFeedback } from "@/components/ai-feedback";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, assetUrl } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import type { AIResponse, AnswerFeedback, QuestionPublic } from "@/types";

const DIFF_BADGE = { easy: "success", medium: "warning", hard: "danger" } as const;

export function QuestionMeta({ q }: { q: QuestionPublic }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      {q.source === "spm_past_year" ? (
        <>
          {q.year && (
            <Badge variant="secondary">
              SPM {q.subject_name ?? ""} {q.year}
            </Badge>
          )}
          {q.paper && <Badge variant="outline">{q.paper}{q.question_number ? ` · Q${q.question_number}` : ""}</Badge>}
        </>
      ) : (
        <Badge variant="secondary" title="Written for practice in the style of SPM; not taken from a real exam paper.">
          {q.source === "teacher" ? "Teacher question" : q.source === "ai_generated" ? "AI-generated" : "Sample question"}
          {q.year ? ` · ${q.year} style` : ""}
        </Badge>
      )}
      {q.topic_name && <Badge variant="muted">{q.topic_name}</Badge>}
      <Badge variant={DIFF_BADGE[q.difficulty]} className="capitalize">
        {q.difficulty}
      </Badge>
      <Badge variant="muted">
        {q.marks} mark{q.marks > 1 ? "s" : ""}
      </Badge>
    </div>
  );
}

export function QuestionCard({
  question,
  feedback,
  onSubmit,
  label,
  showMeta = false,
  allowHints = true,
  footer,
}: {
  question: QuestionPublic;
  feedback?: AnswerFeedback;
  onSubmit: (answer: string) => Promise<void>;
  label?: string;
  showMeta?: boolean;
  allowHints?: boolean;
  footer?: ReactNode;
}) {
  const { aiEnabled } = useAuth();
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setAnswer("");
    setError(null);
  }, [question.id]);

  const submit = async () => {
    if (!answer.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(answer.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit answer");
    } finally {
      setBusy(false);
    }
  };

  const held = !!feedback?.feedback_hidden;
  const chosen = feedback ? feedback.your_answer.toUpperCase() : answer;
  const correctKey = held ? undefined : feedback?.correct_answer.toUpperCase();

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        {label && <p className="text-sm font-bold text-primary">{label}</p>}
        {showMeta && <QuestionMeta q={question} />}
        <p className="whitespace-pre-line text-xl leading-relaxed font-bold">{question.question_text}</p>
        {question.image_url && <img src={assetUrl(question.image_url)} alt="Question diagram" className="max-h-72 rounded-xl border" />}
      </div>

      {question.question_type === "mcq" && question.options ? (
        <div className="grid gap-2.5" role="radiogroup" aria-label="Answer options">
          {question.options.map((o) => {
            const isChosen = chosen === o.key;
            const state = !feedback || held ? (isChosen ? "selected" : held ? "dim" : "idle") : o.key === correctKey ? "correct" : isChosen ? "wrong" : "dim";
            return (
              <button
                key={o.key}
                role="radio"
                aria-checked={isChosen}
                disabled={!!feedback || busy}
                onClick={() => setAnswer(o.key)}
                className={cn(
                  "flex items-center gap-3 rounded-2xl border-2 bg-card px-4 py-3.5 text-left font-semibold transition-all",
                  state === "idle" && "hover:border-primary/40 hover:bg-accent/40",
                  state === "selected" && "border-primary bg-primary/5 shadow-sm",
                  state === "correct" && "border-emerald-500 bg-emerald-50 text-emerald-900",
                  state === "wrong" && "border-orange-400 bg-orange-50 text-orange-900",
                  state === "dim" && "opacity-60",
                )}
              >
                <span
                  className={cn(
                    "flex size-8 shrink-0 items-center justify-center rounded-lg text-sm font-extrabold",
                    state === "selected" ? "bg-primary text-primary-foreground" : state === "correct" ? "bg-emerald-500 text-white" : state === "wrong" ? "bg-orange-400 text-white" : "bg-muted",
                  )}
                >
                  {o.key}
                </span>
                <span className="flex-1">{o.text}</span>
                {state === "correct" && <CheckCircle2 className="size-5 text-emerald-600" aria-label="Correct answer" />}
                {state === "wrong" && <XCircle className="size-5 text-orange-500" aria-label="Your answer" />}
              </button>
            );
          })}
        </div>
      ) : (
        <Input
          value={feedback ? feedback.your_answer : answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          disabled={!!feedback || busy}
          placeholder="Type your answer"
          className="h-12 text-lg"
          aria-label="Your answer"
        />
      )}

      {error && <p className="text-sm text-orange-700">{error}</p>}

      {!feedback ? (
        <div className="space-y-3">
          <Button size="lg" variant="gradient" className="w-full sm:w-auto" onClick={submit} disabled={!answer.trim() || busy}>
            {busy && <Spinner />} Submit answer
          </Button>
          {allowHints && aiEnabled && <HintBox questionId={question.id} />}
        </div>
      ) : held ? (
        <p className="rounded-2xl bg-muted p-4 text-sm font-semibold">Answer saved. Your teacher releases the answers after the due date.</p>
      ) : (
        <FeedbackPanel feedback={feedback} questionId={question.id} />
      )}
      {footer}
    </div>
  );
}

export function FeedbackPanel({ feedback, questionId }: { feedback: AnswerFeedback; questionId: string }) {
  const { aiEnabled } = useAuth();
  return (
    <div className="animate-pop space-y-3">
      {feedback.is_correct ? (
        <div className="flex items-center gap-3 rounded-2xl bg-emerald-50 p-4 text-emerald-900">
          <CheckCircle2 className="size-7 text-emerald-500" />
          <div className="flex-1">
            <p className="font-extrabold">Correct! 🎉</p>
            {feedback.explanation && <p className="text-sm">{feedback.explanation}</p>}
          </div>
          {feedback.xp_gained > 0 && <span className="rounded-full bg-emerald-500 px-3 py-1 text-sm font-bold text-white">+{feedback.xp_gained} XP</span>}
        </div>
      ) : (
        <div className="space-y-2 rounded-2xl bg-orange-50 p-4 text-orange-950">
          <p className="flex items-center gap-2 font-extrabold">
            <XCircle className="size-5 text-orange-500" /> Incorrect
          </p>
          <div className="grid gap-1 text-sm sm:grid-cols-2">
            <p>
              <span className="font-semibold">Your answer:</span> {feedback.your_answer_display}
            </p>
            <p>
              <span className="font-semibold">Correct answer:</span> {feedback.correct_display}
            </p>
          </div>
          {feedback.explanation && (
            <div className="rounded-xl bg-white/70 p-3 text-sm">
              <p className="mb-1 font-bold">Why?</p>
              <p className="whitespace-pre-line">{feedback.explanation}</p>
            </div>
          )}
        </div>
      )}
      {aiEnabled && !feedback.is_correct && <AIExplain attemptId={feedback.attempt_id} questionId={questionId} />}
    </div>
  );
}

function HintBox({ questionId }: { questionId: string }) {
  const [hints, setHints] = useState<AIResponse<{ hint: string; guiding_question: string }>[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => setHints([]), [questionId]);

  const next = async () => {
    setBusy(true);
    try {
      const res = await api.post<AIResponse<{ hint: string; guiding_question: string }>>("/api/ai/hint", { question_id: questionId, level: hints.length + 1 });
      setHints((h) => [...h, res]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-2">
      {hints.map((h, i) => (
        <div key={i} className="animate-pop space-y-1 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
          <p className="flex gap-2 font-semibold">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" /> Hint {i + 1}: {h.data.hint}
          </p>
          <p className="pl-6 text-amber-900/80">🤔 {h.data.guiding_question}</p>
          {i === hints.length - 1 && <AIFeedback interactionId={h.interaction_id} className="pl-6" />}
        </div>
      ))}
      {hints.length < 3 && (
        <Button variant="ghost" size="sm" onClick={next} disabled={busy} className="text-amber-700 hover:bg-amber-50 hover:text-amber-800">
          {busy ? <Spinner /> : <Lightbulb />} {hints.length ? "Another hint" : "Need a hint?"}
        </Button>
      )}
    </div>
  );
}

interface Mistake {
  explanation: string;
  why_wrong: string;
  steps: string[];
  tip: string;
  recommended_action: string;
}

export function AIExplain({ attemptId, questionId }: { attemptId: string; questionId: string }) {
  const [res, setRes] = useState<AIResponse<Mistake> | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      setRes(await api.post<AIResponse<Mistake>>("/api/ai/explain", { attempt_id: attemptId }));
    } finally {
      setBusy(false);
    }
  };

  if (!res)
    return (
      <Button variant="secondary" onClick={load} disabled={busy}>
        {busy ? <Spinner /> : <Bot />} Explain my mistake
      </Button>
    );

  return (
    <div className="animate-pop space-y-3 rounded-2xl border border-violet-200 bg-violet-50/60 p-4 text-sm">
      <p className="flex items-center gap-2 font-bold text-violet-900">
        <Bot className="size-4" /> AI Coach
      </p>
      <p className="text-violet-950">{res.data.why_wrong}</p>
      <ol className="space-y-1.5">
        {res.data.steps.map((s, i) => (
          <li key={i} className="flex gap-2">
            <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-violet-200 text-[11px] font-bold text-violet-800">{i + 1}</span>
            {s}
          </li>
        ))}
      </ol>
      {res.data.tip && <p className="rounded-xl bg-white/70 p-2.5">💡 {res.data.tip}</p>}
      <AIFeedback interactionId={res.interaction_id} />
      <SimilarQuestion questionId={questionId} />
    </div>
  );
}

function SimilarQuestion({ questionId }: { questionId: string }) {
  const [q, setQ] = useState<{ question: QuestionPublic; origin: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [result, setResult] = useState<{ is_correct: boolean; correct_display: string; explanation: string | null } | null>(null);

  const load = async () => {
    setBusy(true);
    setPicked(null);
    setResult(null);
    try {
      setQ(await api.post("/api/ai/similar-question", { question_id: questionId }));
    } finally {
      setBusy(false);
    }
  };

  const check = async (key: string) => {
    if (!q) return;
    setPicked(key);
    setResult(await api.post("/api/ai/similar-question/check", { question_id: q.question.id, answer: key }));
  };

  if (!q)
    return (
      <div className="border-t border-violet-200 pt-3">
        <p className="mb-2 font-semibold text-violet-900">💡 Want another example?</p>
        <Button size="sm" variant="outline" onClick={load} disabled={busy}>
          {busy ? <Spinner /> : <Sparkles />} Give me a similar question
        </Button>
      </div>
    );

  return (
    <div className="space-y-2 border-t border-violet-200 pt-3">
      <p className="text-xs font-bold uppercase tracking-wide text-violet-700">{q.origin === "ai_generated" ? "AI practice question" : "Similar question from the bank"}</p>
      <p className="font-bold">{q.question.question_text}</p>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {q.question.options?.map((o) => (
          <button
            key={o.key}
            disabled={!!picked}
            onClick={() => check(o.key)}
            className={cn(
              "rounded-xl border bg-card px-3 py-2 text-left font-semibold",
              picked === o.key && result && (result.is_correct ? "border-emerald-500 bg-emerald-50" : "border-orange-400 bg-orange-50"),
            )}
          >
            {o.key}. {o.text}
          </button>
        ))}
      </div>
      {result && (
        <p className={cn("rounded-xl p-2.5", result.is_correct ? "bg-emerald-100 text-emerald-900" : "bg-orange-100 text-orange-900")}>
          {result.is_correct ? "🎉 Correct!" : `Not quite — the answer is ${result.correct_display}.`} {result.explanation}
        </p>
      )}
      <Button size="sm" variant="ghost" onClick={load} disabled={busy}>
        {busy ? <Spinner /> : <RefreshCw />} Another one
      </Button>
    </div>
  );
}
