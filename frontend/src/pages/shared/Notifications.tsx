import { useState } from "react";
import { Link } from "react-router-dom";
import { Bell, CheckCheck } from "lucide-react";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { cn, timeAgo } from "@/lib/utils";

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const [unread, setUnread] = useState(false);
  const { data, error, loading, reload, setData } = useApi<NotificationItem[]>(`/api/notifications${unread ? "?unread=true" : ""}`);

  const markRead = async (n: NotificationItem) => {
    if (n.read || !data) return;
    await api.post(`/api/notifications/${n.id}/read`);
    setData(data.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
    window.dispatchEvent(new Event("notifications-changed"));
  };

  const markAll = async () => {
    await api.post("/api/notifications/read-all");
    window.dispatchEvent(new Event("notifications-changed"));
    reload();
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">Notifications</h1>
          <p className="text-muted-foreground">Assignments, exams, memos and replies meant for you.</p>
        </div>
        <Button variant="outline" onClick={markAll}>
          <CheckCheck /> Mark all as read
        </Button>
      </div>
      <div className="flex w-fit gap-1 rounded-xl bg-muted p-1">
        {[false, true].map((u) => (
          <button key={String(u)} onClick={() => setUnread(u)} className={`rounded-lg px-4 py-1.5 text-sm font-semibold ${unread === u ? "bg-card shadow-sm" : "text-muted-foreground"}`}>
            {u ? "Unread" : "All"}
          </button>
        ))}
      </div>
      {loading && !data && <PageLoader rows={2} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && data.length === 0 && <EmptyState emoji="🔔" title={unread ? "You're all caught up" : "No notifications yet"} />}
      <div className="space-y-2">
        {data?.map((n) => {
          const content = (
            <Card className={cn("flex-row items-start gap-3 p-4", !n.read && "border-primary/40 bg-primary/5")}>
              <Bell className={cn("mt-0.5 size-4 shrink-0", n.read ? "text-muted-foreground" : "text-primary")} />
              <div className="min-w-0 flex-1">
                <p className={cn("text-sm", !n.read && "font-bold")}>{n.title}</p>
                {n.body && <p className="truncate text-sm text-muted-foreground">{n.body}</p>}
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(n.created_at)}</span>
            </Card>
          );
          return n.link ? (
            <Link key={n.id} to={n.link} onClick={() => markRead(n)} className="block">
              {content}
            </Link>
          ) : (
            <button key={n.id} onClick={() => markRead(n)} className="block w-full text-left">
              {content}
            </button>
          );
        })}
      </div>
    </div>
  );
}
