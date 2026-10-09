import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({ icon: Icon, label, value, hint, tone = "violet" }: { icon: LucideIcon; label: string; value: string; hint?: string; tone?: "violet" | "emerald" | "orange" | "sky" }) {
  const tones = {
    violet: "from-violet-500 to-indigo-500",
    emerald: "from-emerald-500 to-teal-500",
    orange: "from-orange-400 to-rose-500",
    sky: "from-sky-400 to-blue-500",
  };
  return (
    <Card className="flex-row items-center gap-4 p-4">
      <div className={cn("flex size-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white", tones[tone])}>
        <Icon className="size-5" />
      </div>
      <div className="min-w-0">
        <p className="text-2xl font-extrabold tabular-nums">{value}</p>
        <p className="truncate text-xs font-semibold text-muted-foreground">{label}</p>
        {hint && <p className="truncate text-[11px] text-muted-foreground">{hint}</p>}
      </div>
    </Card>
  );
}
