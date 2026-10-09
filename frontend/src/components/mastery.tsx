import { AlertTriangle, CheckCircle2, Circle, CircleDashed, CircleDot, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LevelKey } from "@/types";

export const LEVEL_STYLE: Record<LevelKey, { label: string; icon: LucideIcon; text: string; bg: string; bar: string; hex: string }> = {
  mastered: { label: "Mastered", icon: CheckCircle2, text: "text-emerald-700", bg: "bg-emerald-50 border-emerald-200", bar: "from-emerald-400 to-emerald-600", hex: "#10b981" },
  good: { label: "Good", icon: CircleDot, text: "text-sky-700", bg: "bg-sky-50 border-sky-200", bar: "from-sky-400 to-sky-600", hex: "#0ea5e9" },
  developing: { label: "Developing", icon: CircleDashed, text: "text-amber-700", bg: "bg-amber-50 border-amber-200", bar: "from-amber-300 to-amber-500", hex: "#f59e0b" },
  needs_attention: { label: "Needs Attention", icon: AlertTriangle, text: "text-orange-700", bg: "bg-orange-50 border-orange-200", bar: "from-orange-400 to-rose-500", hex: "#f97316" },
  not_started: { label: "Not Started", icon: Circle, text: "text-slate-500", bg: "bg-slate-50 border-slate-200", bar: "from-slate-300 to-slate-400", hex: "#94a3b8" },
};

export function levelFor(mastery: number | null | undefined, attempts = 1): LevelKey {
  if (mastery == null || attempts === 0) return "not_started";
  if (mastery >= 80) return "mastered";
  if (mastery >= 60) return "good";
  if (mastery >= 40) return "developing";
  return "needs_attention";
}

export function MasteryBadge({ level, className, compact }: { level: LevelKey; className?: string; compact?: boolean }) {
  const s = LEVEL_STYLE[level];
  const Icon = s.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold", s.bg, s.text, className)}>
      <Icon className="size-3.5" aria-hidden />
      {compact ? <span className="sr-only">{s.label}</span> : s.label}
    </span>
  );
}

export function MasteryBar({ value, level, className }: { value: number; level: LevelKey; className?: string }) {
  return (
    <div className={cn("bg-muted h-2 w-full overflow-hidden rounded-full", className)} role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className={cn("h-full rounded-full bg-gradient-to-r transition-all duration-700", LEVEL_STYLE[level].bar)} style={{ width: `${Math.max(value, level === "not_started" ? 0 : 3)}%` }} />
    </div>
  );
}

export function MasteryCell({ value }: { value: number | null }) {
  const level = levelFor(value);
  const s = LEVEL_STYLE[level];
  const Icon = s.icon;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-bold tabular-nums", value == null ? "text-slate-400" : s.text, value != null && s.bg.split(" ")[0])}>
      {value != null && <Icon className="size-3" aria-label={s.label} />}
      {value == null ? "—" : `${Math.round(value)}%`}
    </span>
  );
}
