import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Paperclip } from "lucide-react";
import { api } from "@/lib/api";
import { AttachmentList, type Attachment } from "@/pages/shared/Memos";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { ErrorState, PageLoader } from "@/components/states";
import { PageHeader, errorText, refreshAdmin } from "./common";

type Memo = { id: string; title: string; audience: string; status: string; requires_acknowledgement: boolean; read_count: number; acknowledgement_count: number; attachments: Attachment[] };

export default function AdminMemosPage() {
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState("all");
  const [ack, setAck] = useState(false);
  const memos = useQuery({ queryKey: ["admin", "memos"], queryFn: () => api.get<Memo[]>("/api/admin/memos") });

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await refreshAdmin();
    } catch (e) {
      setError(errorText(e));
    }
  };

  if (memos.isPending) return <PageLoader />;
  if (memos.error || !memos.data) return <ErrorState message={memos.error?.message ?? "Could not load"} onRetry={() => memos.refetch()} />;

  return (
    <div className="space-y-6">
      <PageHeader title="Memos" description="Drafts stay private. Publishing notifies the audience. Archived memos disappear from inboxes but the acknowledgement record stays." />
      <Card>
        <form className="space-y-3" onSubmit={(e) => {
          e.preventDefault();
          void run(async () => {
            await api.post("/api/admin/memos", { title, body, audience, requires_acknowledgement: ack });
            setTitle(""); setBody("");
          });
        }}>
          <Input aria-label="Title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Textarea aria-label="Memo" placeholder="Write the memo" value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="flex flex-wrap items-center gap-3">
            <Select aria-label="Audience" value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="all">Everyone</option>
              <option value="teachers">Teachers</option>
              <option value="students">Students</option>
            </Select>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> Ask for acknowledgement</label>
            <Button type="submit" disabled={!title.trim() || !body.trim()}>Save draft</Button>
          </div>
        </form>
        {error && <p className="mt-2 text-sm text-orange-700">{error}</p>}
      </Card>
      <ul className="space-y-2">
        {memos.data.map((m) => (
          <li key={m.id} className="space-y-2 rounded-xl border px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-semibold">{m.title}</p>
                <p className="text-xs text-muted-foreground">{m.status} · {m.audience} · {m.read_count} read · {m.acknowledgement_count} acknowledged</p>
              </div>
              <span className="flex flex-wrap items-center gap-2">
                {m.status !== "published" && <Button size="sm" onClick={() => run(() => api.post(`/api/admin/memos/${m.id}/status`, { status: "published" }))}>Publish</Button>}
                {m.status !== "archived" && <Button size="sm" variant="outline" onClick={() => run(() => api.post(`/api/admin/memos/${m.id}/status`, { status: "archived" }))}>Archive</Button>}
                {m.status !== "archived" && m.attachments.length < 5 && (
                  <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-lg border px-3 text-xs font-semibold hover:bg-muted">
                    <Paperclip className="size-4" /> Attach
                    <input
                      type="file"
                      accept="application/pdf,image/png,image/jpeg,image/webp,image/gif"
                      className="sr-only"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        e.target.value = "";
                        if (file) void run(() => api.upload(`/api/admin/memos/${m.id}/attachments`, file));
                      }}
                    />
                  </label>
                )}
                <Button size="sm" variant="ghost" onClick={() => run(() => api.download(`/api/admin/memos/${m.id}/acknowledgements`, "acknowledgements.csv"))}>Report</Button>
              </span>
            </div>
            {m.attachments.length > 0 && (
              <AttachmentList
                attachments={m.attachments}
                onRemove={m.status === "archived" ? undefined : (a) => run(() => api.del(`/api/admin/memos/${m.id}/attachments/${a.id}`))}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
