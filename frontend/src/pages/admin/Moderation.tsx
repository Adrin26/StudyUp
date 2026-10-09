import { useState } from "react";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";

interface ReportGroup {
  target_type: "post" | "comment";
  target_id: string;
  post_id: string;
  space: "student" | "teacher";
  post_title: string;
  body: string;
  author: { id: string; name: string; role: string } | null;
  status: "visible" | "hidden";
  moderation_reason: string | null;
  created_at: string;
  reports: { id: string; reason_label: string; details: string | null; reporter: string | null; status: string; created_at: string }[];
}

export default function ModerationPage() {
  const [state, setState] = useState<"open" | "closed">("open");
  const { data, error, loading, reload } = useApi<ReportGroup[]>(`/api/community/reports?state=${state}`);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Community moderation</h1>
        <p className="text-muted-foreground">
          Reports on your school's student community and on posts by your school's teachers. Content reported by three people is hidden automatically until you review it.
        </p>
      </div>
      <div className="flex w-fit gap-1 rounded-xl bg-muted p-1">
        {(["open", "closed"] as const).map((s) => (
          <button key={s} onClick={() => setState(s)} className={`rounded-lg px-4 py-1.5 text-sm font-semibold ${state === s ? "bg-card shadow-sm" : "text-muted-foreground"}`}>
            {s === "open" ? "Needs review" : "Resolved"}
          </button>
        ))}
      </div>
      {loading && !data && <PageLoader rows={2} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState emoji="✅" title={state === "open" ? "Nothing to review" : "No resolved reports yet"} />}
      <div className="space-y-3">
        {data?.map((g) => (
          <ReportCard key={g.target_id} group={g} open={state === "open"} onDone={reload} />
        ))}
      </div>
    </div>
  );
}

function ReportCard({ group: g, open, onDone }: { group: ReportGroup; open: boolean; onDone: () => void }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const base = g.target_type === "post" ? `/api/community/posts/${g.target_id}` : `/api/community/comments/${g.target_id}`;

  const act = async (action: "hide" | "restore" | "dismiss") => {
    setBusy(action);
    setError(null);
    try {
      await api.post(`${base}/moderation`, { action, reason: reason || null });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="secondary">{g.space === "student" ? "Student community" : "Teacher community"}</Badge>
        <Badge variant="outline" className="capitalize">{g.target_type}</Badge>
        {g.status === "hidden" && <Badge variant="danger">Hidden</Badge>}
        <span className="text-xs text-muted-foreground">
          by {g.author?.name ?? "deleted user"} · {timeAgo(g.created_at)}
        </span>
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{g.target_type === "comment" ? `Comment on “${g.post_title}”` : g.post_title}</p>
        <p className="mt-1 rounded-xl bg-muted/60 p-3 text-sm whitespace-pre-line">{g.body}</p>
        {g.moderation_reason && <p className="mt-1 text-xs text-muted-foreground">Moderation note: {g.moderation_reason}</p>}
      </div>
      <ul className="space-y-1 text-sm">
        {g.reports.map((r) => (
          <li key={r.id}>
            <span className="font-semibold">{r.reason_label}</span>
            {r.details && ` — ${r.details}`}
            <span className="text-xs text-muted-foreground">
              {" "}
              · {r.reporter ?? "unknown"} · {timeAgo(r.created_at)}
              {!open && ` · ${r.status}`}
            </span>
          </li>
        ))}
      </ul>
      {open ? (
        <div className="flex flex-wrap items-center gap-2">
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Note to the author (optional)" className="max-w-xs" maxLength={300} aria-label="Moderation note" />
          {g.status === "visible" ? (
            <>
              <Button variant="gradient" size="sm" onClick={() => act("hide")} disabled={!!busy}>
                {busy === "hide" && <Spinner />} Hide
              </Button>
              <Button variant="outline" size="sm" onClick={() => act("dismiss")} disabled={!!busy}>
                {busy === "dismiss" && <Spinner />} Keep visible
              </Button>
            </>
          ) : (
            <>
              <Button variant="gradient" size="sm" onClick={() => act("hide")} disabled={!!busy}>
                {busy === "hide" && <Spinner />} Keep hidden
              </Button>
              <Button variant="outline" size="sm" onClick={() => act("restore")} disabled={!!busy}>
                {busy === "restore" && <Spinner />} Restore
              </Button>
            </>
          )}
        </div>
      ) : (
        g.status === "hidden" && (
          <Button variant="outline" size="sm" className="w-fit" onClick={() => act("restore")} disabled={!!busy}>
            {busy === "restore" && <Spinner />} Restore
          </Button>
        )
      )}
      {error && <p className="text-sm text-orange-700">{error}</p>}
    </Card>
  );
}
