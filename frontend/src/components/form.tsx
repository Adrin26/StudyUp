import type { ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";
import { Label } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function Field({ id, label, error, hint, children }: { id: string; label: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {error ? (
        <p id={`${id}-error`} className="text-sm font-medium text-orange-700" role="alert">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  );
}

export function FormAlert({ tone = "error", children }: { tone?: "error" | "success" | "info"; children: ReactNode }) {
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cn(
        "flex items-start gap-2 rounded-xl px-3 py-2 text-sm font-medium",
        tone === "error" && "bg-orange-50 text-orange-800",
        tone === "success" && "bg-emerald-50 text-emerald-800",
        tone === "info" && "bg-sky-50 text-sky-800",
      )}
    >
      {tone === "success" && <CheckCircle2 className="mt-0.5 size-4 shrink-0" />}
      <span>{children}</span>
    </div>
  );
}
