import { useState } from "react";
import { CheckCircle2, Lightbulb, Sparkles, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Slide } from "@/types";

const TYPE_LABEL: Record<Slide["type"], { label: string; className: string }> = {
  intro: { label: "Introduction", className: "bg-violet-100 text-violet-700" },
  concept: { label: "Key concept", className: "bg-sky-100 text-sky-700" },
  formula: { label: "Formula", className: "bg-indigo-100 text-indigo-700" },
  example: { label: "Worked example", className: "bg-emerald-100 text-emerald-700" },
  tip: { label: "Pro tip", className: "bg-amber-100 text-amber-800" },
  try: { label: "Try it yourself", className: "bg-fuchsia-100 text-fuchsia-700" },
};

export function SlideView({ slide }: { slide: Slide }) {
  const c = slide.content;
  const tag = TYPE_LABEL[slide.type];
  return (
    <div key={slide.id} className="animate-in fade-in slide-in-from-right-4 space-y-6 duration-300">
      <span className={cn("inline-flex rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide", tag.className)}>{tag.label}</span>
      <div className="flex items-start gap-4">
        {c.emoji && <span className="text-5xl" aria-hidden>{c.emoji}</span>}
        <h2 className="text-2xl font-extrabold tracking-tight text-balance sm:text-3xl">{slide.title}</h2>
      </div>
      {c.body && <p className="text-lg leading-relaxed text-foreground/85">{c.body}</p>}

      {c.formula && (
        <div className="rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 p-6 text-center text-white shadow-lg shadow-indigo-500/20">
          <p className="font-mono text-2xl font-bold tracking-wide sm:text-3xl">{c.formula}</p>
        </div>
      )}

      {c.highlight && (
        <div className="flex gap-3 rounded-2xl border-2 border-dashed border-violet-300 bg-violet-50 p-4 text-violet-950">
          <Sparkles className="mt-0.5 size-5 shrink-0 text-violet-500" />
          <p className="font-semibold">{c.highlight}</p>
        </div>
      )}

      {c.example && (
        <div className="space-y-4 rounded-2xl border bg-card p-5">
          <p className="text-lg font-bold">{c.example}</p>
          {c.steps && (
            <ol className="space-y-3">
              {c.steps.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-bold text-emerald-700">{i + 1}</span>
                  <span className="pt-0.5">{s}</span>
                </li>
              ))}
            </ol>
          )}
          {c.answer != null && slide.type !== "try" && <p className="rounded-xl bg-emerald-50 px-4 py-3 font-mono text-lg font-bold text-emerald-800">✓ {c.answer}</p>}
        </div>
      )}

      {c.points && (
        <ul className="grid gap-2">
          {c.points.map((p, i) => (
            <li key={i} className="flex gap-3 rounded-xl bg-muted/60 px-4 py-3">
              <span className="mt-2 size-2 shrink-0 rounded-full bg-primary" />
              <span>{p}</span>
            </li>
          ))}
        </ul>
      )}

      {c.note && (
        <p className="flex gap-2 rounded-xl bg-amber-50 px-4 py-3 text-amber-950">
          <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-600" /> {c.note}
        </p>
      )}

      {slide.type === "try" && c.question && <TryIt slide={slide} />}
    </div>
  );
}

function TryIt({ slide }: { slide: Slide }) {
  const c = slide.content;
  const [picked, setPicked] = useState<number | null>(null);
  const correct = typeof c.answer === "number" ? c.answer : 0;
  return (
    <div className="space-y-4 rounded-2xl border-2 border-fuchsia-200 bg-fuchsia-50/50 p-5">
      <p className="text-lg font-bold">{c.question}</p>
      <div className="grid gap-2 sm:grid-cols-2">
        {c.options?.map((o, i) => {
          const state = picked === null ? "idle" : i === correct ? "correct" : i === picked ? "wrong" : "idle";
          return (
            <button
              key={i}
              disabled={picked !== null}
              onClick={() => setPicked(i)}
              className={cn(
                "flex items-center gap-2 rounded-xl border-2 bg-card px-4 py-3 text-left font-semibold transition-all",
                state === "idle" && "hover:border-primary/50",
                state === "correct" && "border-emerald-500 bg-emerald-50 text-emerald-800",
                state === "wrong" && "border-orange-400 bg-orange-50 text-orange-800",
              )}
            >
              {state === "correct" && <CheckCircle2 className="size-5" />}
              {state === "wrong" && <XCircle className="size-5" />}
              {o}
            </button>
          );
        })}
      </div>
      {picked !== null && (
        <p className={cn("animate-pop rounded-xl px-4 py-3 text-sm font-medium", picked === correct ? "bg-emerald-100 text-emerald-900" : "bg-orange-100 text-orange-900")}>
          {picked === correct ? "🎉 Nice! " : "Not quite. "}
          {c.explanation}
        </p>
      )}
    </div>
  );
}
