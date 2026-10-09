import type { ReactNode } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/checkbox";

export function PageLoader({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-36 w-full" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-40" />
        ))}
      </div>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={`animate-spin ${className ?? "size-4"}`} aria-hidden />;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed p-10 text-center">
      <AlertCircle className="size-10 text-orange-500" />
      <div>
        <p className="font-semibold">Something went wrong</p>
        <p className="text-muted-foreground text-sm">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({ emoji, title, description, action }: { emoji: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed bg-card/50 p-10 text-center">
      <div className="animate-float text-5xl" aria-hidden>
        {emoji}
      </div>
      <div>
        <p className="text-lg font-bold">{title}</p>
        {description && <p className="text-muted-foreground mx-auto max-w-sm text-sm">{description}</p>}
      </div>
      {action}
    </div>
  );
}
