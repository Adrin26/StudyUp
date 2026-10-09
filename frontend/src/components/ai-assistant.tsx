import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Lightbulb, Send, Sparkles } from "lucide-react";
import { AIFeedback } from "@/components/ai-feedback";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { AIResponse } from "@/types";

interface LessonHelp {
  explanation: string;
  example: string;
  hint: string;
  check_question: string;
}

type Message = { role: "user"; text: string } | { role: "ai"; res: AIResponse<LessonHelp> } | { role: "error"; text: string };

const QUICK = ["I don't understand this.", "Can you explain this more simply?", "Give me another example.", "Give me a hint."];

export function AIAssistant({ topicId, slideId, slideTitle }: { topicId: string; slideId?: string; slideTitle?: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const ask = async (text: string, e?: FormEvent) => {
    e?.preventDefault();
    const message = text.trim();
    if (!message || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: message }]);
    setBusy(true);
    try {
      const res = await api.post<AIResponse<LessonHelp>>("/api/ai/lesson-help", { topic_id: topicId, slide_id: slideId, message });
      setMessages((m) => [...m, { role: "ai", res }]);
    } catch (err) {
      setMessages((m) => [...m, { role: "error", text: err instanceof Error ? err.message : "The coach is unavailable right now." }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-3 border-b p-4">
        <div className="flex size-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white">
          <Bot className="size-5" />
        </div>
        <div>
          <p className="font-bold">AI Study Coach</p>
          <p className="text-xs text-muted-foreground">{slideTitle ? `Helping with: ${slideTitle}` : "Ask me anything about this lesson"}</p>
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="rounded-2xl bg-violet-50 p-4 text-sm text-violet-950">
            <p className="font-semibold">Hi! 👋 Stuck on something?</p>
            <p className="mt-1 text-violet-900/80">I'll explain step by step and give you hints — you do the thinking. 💪</p>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground">
              {m.text}
            </div>
          ) : m.role === "error" ? (
            <div key={i} className="rounded-2xl bg-orange-50 px-4 py-2 text-sm text-orange-800">
              {m.text}
            </div>
          ) : (
            <div key={i} className="animate-pop space-y-3 rounded-2xl rounded-bl-md border bg-card p-4 text-sm shadow-sm">
              <p className="leading-relaxed">{m.res.data.explanation}</p>
              {m.res.data.example && (
                <div className="rounded-xl bg-sky-50 p-3 text-sky-950">
                  <p className="mb-1 text-xs font-bold uppercase tracking-wide text-sky-700">Example</p>
                  <p className="whitespace-pre-line">{m.res.data.example}</p>
                </div>
              )}
              {m.res.data.hint && (
                <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-amber-950">
                  <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" /> {m.res.data.hint}
                </p>
              )}
              {m.res.data.check_question && (
                <p className="text-xs font-semibold text-muted-foreground">
                  <Sparkles className="mr-1 inline size-3.5 text-violet-500" />
                  Quick check: {m.res.data.check_question}
                </p>
              )}
              <AIFeedback interactionId={m.res.interaction_id} />
            </div>
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner /> Thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="space-y-2 border-t p-3">
        <div className="flex flex-wrap gap-1.5">
          {QUICK.map((q) => (
            <button key={q} onClick={() => ask(q)} disabled={busy} className="rounded-full border bg-card px-3 py-1 text-xs font-semibold hover:border-primary/40 hover:bg-accent disabled:opacity-50">
              {q}
            </button>
          ))}
        </div>
        <form onSubmit={(e) => ask(input, e)} className="flex gap-2">
          <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask a question…" maxLength={600} aria-label="Ask the AI coach" />
          <Button type="submit" size="icon" disabled={busy || !input.trim()} aria-label="Send">
            <Send />
          </Button>
        </form>
      </div>
    </div>
  );
}
