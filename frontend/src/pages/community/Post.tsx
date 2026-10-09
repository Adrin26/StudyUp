import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bookmark, Flag, GraduationCap, Reply, Trash2 } from "lucide-react";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { VoteButton } from "@/components/vote-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Label, Select, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";
import type { PostComment, PostDetail } from "@/types";

export default function PostPage() {
  const { postId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: post, error, loading, reload, setData } = useApi<PostDetail>(`/api/community/posts/${postId}`);

  if (loading && !post) return <PageLoader rows={1} />;
  if (error || !post) return <ErrorState message={error ?? "Post not found"} onRetry={reload} />;

  const back = user?.role === "student" ? "/community" : post.space === "teacher" ? "/teacher/community" : "/teacher/student-community";
  const topLevel = post.comments.filter((c) => !c.parent_id);
  const repliesTo = (id: string) => post.comments.filter((c) => c.parent_id === id);

  const addComment = (c: PostComment) => setData({ ...post, comments: [...post.comments, c], comment_count: post.comment_count + 1 });

  const removePost = async () => {
    if (!confirm("Delete this post?")) return;
    await api.del(`/api/community/posts/${post.id}`);
    navigate(back);
  };

  const removeComment = async (c: PostComment) => {
    if (!confirm("Delete this comment and its replies?")) return;
    await api.del(`/api/community/comments/${c.id}`);
    reload();
  };

  const toggleBookmark = async () => {
    if (post.bookmarked) await api.del(`/api/community/posts/${post.id}/bookmark`);
    else await api.put(`/api/community/posts/${post.id}/bookmark`);
    setData({ ...post, bookmarked: !post.bookmarked });
  };

  const comment = (c: PostComment, isReply = false) => (
    <Card key={c.id} className={`gap-2 p-4 ${isReply ? "ml-6 sm:ml-10" : ""}`}>
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {c.author.role === "teacher" && <GraduationCap className="size-3.5 text-emerald-600" />}
        <span className="font-semibold text-foreground">{c.author.name}</span> · {timeAgo(c.created_at)}
        {c.status === "hidden" && <Badge variant="danger">Hidden{c.moderation_reason ? `: ${c.moderation_reason}` : ""}</Badge>}
      </p>
      <p className="text-sm leading-relaxed whitespace-pre-line">{c.body}</p>
      <div className="flex flex-wrap gap-1">
        {!isReply && post.can_comment && c.status === "visible" && <CommentForm postId={post.id} parentId={c.id} onAdded={addComment} compact />}
        {c.author.id !== user?.id && c.status === "visible" && <ReportDialog url={`/api/community/comments/${c.id}/report`} what="comment" />}
        {c.author.id === user?.id && (
          <Button variant="ghost" size="sm" onClick={() => removeComment(c)} className="text-muted-foreground">
            <Trash2 /> Delete
          </Button>
        )}
      </div>
    </Card>
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to={back} className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to community
      </Link>

      {post.status === "hidden" && (
        <p className="rounded-2xl bg-orange-50 p-4 text-sm text-orange-900">
          A moderator hid this post{post.moderation_reason ? `: ${post.moderation_reason}` : "."} Only you and the school admin can see it.
        </p>
      )}

      <Card className="flex-row gap-3">
        <VoteButton postId={post.id} score={post.score} myVote={post.my_vote} vertical disabled={!post.can_vote} />
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {post.subject && <Badge variant="secondary">{post.subject}</Badge>}
            {post.topic && <Badge variant="muted">{post.topic}</Badge>}
            {post.category && <Badge variant="outline">{post.category}</Badge>}
          </div>
          <h1 className="text-xl font-extrabold sm:text-2xl">{post.title}</h1>
          <p className="text-xs text-muted-foreground">
            Posted by <span className="font-semibold text-foreground">{post.author.name}</span> · {timeAgo(post.created_at)}
          </p>
          <p className="leading-relaxed whitespace-pre-line">{post.body}</p>
          <div className="flex flex-wrap gap-1">
            <Button variant="ghost" size="sm" onClick={toggleBookmark} aria-pressed={post.bookmarked} className="text-muted-foreground">
              <Bookmark className={post.bookmarked ? "fill-current text-primary" : ""} /> {post.bookmarked ? "Saved" : "Save"}
            </Button>
            {post.can_report && <ReportDialog url={`/api/community/posts/${post.id}/report`} what="post" />}
            {post.author.id === user?.id && (
              <Button variant="ghost" size="sm" onClick={removePost} className="text-muted-foreground">
                <Trash2 /> Delete
              </Button>
            )}
          </div>
        </div>
      </Card>

      <h2 className="font-extrabold">💬 {post.comment_count} comments</h2>

      {post.can_comment && <CommentForm postId={post.id} onAdded={addComment} />}

      <div className="space-y-2">
        {topLevel.map((c) => (
          <div key={c.id} className="space-y-2">
            {comment(c)}
            {repliesTo(c.id).map((r) => comment(r, true))}
          </div>
        ))}
      </div>
    </div>
  );
}

function CommentForm({ postId, parentId, onAdded, compact }: { postId: string; parentId?: string; onAdded: (c: PostComment) => void; compact?: boolean }) {
  const [open, setOpen] = useState(!compact);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open)
    return (
      <Button variant="ghost" size="sm" onClick={() => setOpen(true)} className="text-muted-foreground">
        <Reply /> Reply
      </Button>
    );

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    setError(null);
    try {
      onAdded(await api.post<PostComment>(`/api/community/posts/${postId}/comments`, { body, parent_id: parentId ?? null }));
      setBody("");
      if (compact) setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not post your reply");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="w-full space-y-2">
      <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write a helpful reply…" rows={compact ? 2 : 3} aria-label="Comment" />
      {error && <p className="text-sm text-orange-700">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size={compact ? "sm" : "default"} disabled={busy || !body.trim()}>
          {busy && <Spinner />} Reply
        </Button>
        {compact && (
          <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

function ReportDialog({ url, what }: { url: string; what: "post" | "comment" }) {
  const { data: meta } = useApi<{ report_reasons: { value: string; label: string }[] }>("/api/community/meta");
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("inappropriate");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(url, { reason, details: details || null });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the report");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground">
          <Flag /> Report
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Report this {what}</DialogTitle>
          <DialogDescription>Your school admin reviews reports. The author is not told who reported it.</DialogDescription>
        </DialogHeader>
        {done ? (
          <div className="space-y-3">
            <p className="font-semibold">Thanks — the report was sent.</p>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="r-reason">Reason</Label>
              <Select id="r-reason" value={reason} onChange={(e) => setReason(e.target.value)}>
                {meta?.report_reasons.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="r-details">Details (optional)</Label>
              <Textarea id="r-details" value={details} onChange={(e) => setDetails(e.target.value)} maxLength={500} rows={3} />
            </div>
            {error && <p className="text-sm text-orange-700">{error}</p>}
            <Button type="submit" variant="gradient" className="w-full" disabled={busy}>
              {busy && <Spinner />} Send report
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
