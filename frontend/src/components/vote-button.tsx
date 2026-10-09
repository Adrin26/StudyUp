import { useState } from "react";
import { ArrowBigUp } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function VoteButton({ postId, score, myVote, vertical, disabled }: { postId: string; score: number; myVote: number; vertical?: boolean; disabled?: boolean }) {
  const [state, setState] = useState({ score, myVote });
  const toggle = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    const value = state.myVote === 1 ? 0 : 1;
    const optimistic = { score: state.score + (value === 1 ? 1 : -1), myVote: value };
    setState(optimistic);
    try {
      const res = await api.post<{ score: number; my_vote: number }>(`/api/community/posts/${postId}/vote`, { value });
      setState({ score: res.score, myVote: res.my_vote });
    } catch {
      setState({ score, myVote });
    }
  };
  return (
    <button
      onClick={toggle}
      aria-pressed={state.myVote === 1}
      aria-disabled={disabled}
      aria-label={disabled ? `Score ${state.score}` : `Upvote (${state.score})`}
      className={cn(
        "flex items-center gap-1 rounded-xl px-2 py-1 text-sm font-bold transition-colors",
        vertical && "flex-col gap-0 px-2.5 py-2",
        state.myVote === 1 ? "bg-violet-100 text-violet-700" : "text-muted-foreground",
        !disabled && state.myVote !== 1 && "hover:bg-muted",
        disabled && "cursor-default",
      )}
    >
      <ArrowBigUp className={cn("size-5", state.myVote === 1 && "fill-current")} />
      {state.score}
    </button>
  );
}
