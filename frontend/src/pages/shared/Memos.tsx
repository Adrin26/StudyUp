import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Paperclip, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { queryClient } from "@/lib/query";

export type Attachment = { id: string; filename: string; url: string };

type Memo = {
  id: string; title: string; body: string; requires_acknowledgement: boolean; read: boolean; acknowledged: boolean;
  publish_at: string | null; attachments: Attachment[];
};

export default function MemosPage() {
  const { memoId } = useParams();
  if (memoId) return <MemoDetail id={memoId} />;
  return <MemoList />;
}

function MemoList() {
  const memos = useQuery({ queryKey: ["memos"], queryFn: () => api.get<Memo[]>("/api/memos") });
  if (memos.isPending) return <PageLoader />;
  if (memos.error || !memos.data) return <ErrorState message={memos.error?.message ?? "Could not load"} onRetry={() => memos.refetch()} />;
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-extrabold">Memos</h1>
      {memos.data.length === 0 ? <EmptyState emoji="📌" title="No memos" description="Published school memos show up here." /> : (
        <ul className="divide-y rounded-xl border">
          {memos.data.map((m) => (
            <li key={m.id}>
              <Link to={`/memos/${m.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-muted">
                <span className="font-semibold">{m.title}</span>
                {!m.read && <span className="text-xs font-semibold text-primary">New</span>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MemoDetail({ id }: { id: string }) {
  const memo = useQuery({ queryKey: ["memos", id], queryFn: () => api.get<Memo>(`/api/memos/${id}`) });
  if (memo.isPending) return <PageLoader />;
  if (memo.error || !memo.data) return <ErrorState message={memo.error?.message ?? "Memo not found"} onRetry={() => memo.refetch()} />;
  const m = memo.data;
  return (
    <Card className="space-y-4">
      <Link to="/memos" className="text-sm font-semibold text-muted-foreground">All memos</Link>
      <h1 className="text-2xl font-extrabold">{m.title}</h1>
      <p className="whitespace-pre-wrap">{m.body}</p>
      {m.attachments.length > 0 && <AttachmentList attachments={m.attachments} />}
      {m.requires_acknowledgement && !m.acknowledged && (
        <Button onClick={async () => { await api.post(`/api/memos/${id}/acknowledge`); await queryClient.invalidateQueries({ queryKey: ["memos"] }); }}>I have read this</Button>
      )}
      {m.acknowledged && <p className="text-sm text-emerald-700">Acknowledged.</p>}
    </Card>
  );
}

export function AttachmentList({ attachments, onRemove }: { attachments: Attachment[]; onRemove?: (a: Attachment) => void }) {
  const [error, setError] = useState<string | null>(null);
  const open = async (a: Attachment) => {
    setError(null);
    try {
      await api.download(a.url, a.filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not download the file.");
    }
  };
  return (
    <div className="space-y-1">
      <ul className="space-y-1">
        {attachments.map((a) => (
          <li key={a.id} className="flex items-center gap-2 text-sm">
            <button type="button" onClick={() => open(a)} className="flex min-w-0 items-center gap-1.5 font-semibold text-primary hover:underline">
              <Paperclip className="size-4 shrink-0" />
              <span className="truncate">{a.filename}</span>
            </button>
            {onRemove && (
              <button type="button" onClick={() => onRemove(a)} className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label={`Remove ${a.filename}`}>
                <X className="size-3.5" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {error && <p className="text-sm text-orange-700">{error}</p>}
    </div>
  );
}
