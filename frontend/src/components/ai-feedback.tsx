import { useState } from "react";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function AIFeedback({ interactionId, className }: { interactionId: string; className?: string }) {
  const [value, setValue] = useState<boolean | null>(null);
  const send = async (helpful: boolean) => {
    setValue(helpful);
    try {
      await api.post("/api/ai/feedback", { interaction_id: interactionId, helpful });
    } catch {
      setValue(null);
    }
  };
  if (value !== null) {
    return <p className={cn("text-xs font-medium text-muted-foreground", className)}>Thanks for the feedback! {value ? "🙌" : "We'll keep improving."}</p>;
  }
  return (
    <div className={cn("flex items-center gap-2 text-xs font-medium text-muted-foreground", className)}>
      Was this explanation helpful?
      <button onClick={() => send(true)} className="inline-flex items-center gap-1 rounded-lg border bg-card px-2 py-1 hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700">
        <ThumbsUp className="size-3.5" /> Yes
      </button>
      <button onClick={() => send(false)} className="inline-flex items-center gap-1 rounded-lg border bg-card px-2 py-1 hover:border-orange-300 hover:bg-orange-50 hover:text-orange-700">
        <ThumbsDown className="size-3.5" /> No
      </button>
    </div>
  );
}
