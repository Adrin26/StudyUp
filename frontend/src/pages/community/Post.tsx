import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, GraduationCap, Trash2 } from "lucide-react";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { VoteButton } from "@/components/vote-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";
import type { PostDetail } from "@/types";

export default function PostPage() {
  const { postId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: post, error, loading, reload, setData } = useApi<PostDetail>(`/api/community/posts/${postId}`);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading && !post) return <PageLoader rows={1} />;
  if (error || !post) return <ErrorState message={error ?? "Post not found"} onRetry={reload} />;

  const back = user?.role === "student" ? "/community" : post.space === "teacher" ? "/teacher/community" : "/teacher/student-community";

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) return;
    setBusy(true);
    try {
      const c = await api.post<PostDetail["comments"][number]>(`/api/community/posts/${post.id}/comments`, { body: comment });
      setData({ ...post, comments: [...post.comments, c], comment_count: post.comment_count + 1 });
      setComment("");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!confirm("Delete this post?")) return;
    await api.del(`/api/community/posts/${post.id}`);
    navigate(back);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link to={back} className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Back to community
      </Link>

      <Card className="flex-row gap-3">
        <VoteButton postId={post.id} score={post.score} myVote={post.my_vote} vertical />
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
          {post.author.id === user?.id && (
            <Button variant="ghost" size="sm" onClick={remove} className="text-muted-foreground">
              <Trash2 /> Delete
            </Button>
          )}
        </div>
      </Card>

      <h2 className="font-extrabold">💬 {post.comment_count} comments</h2>

      {post.can_comment && (
        <form onSubmit={submit} className="space-y-2">
          <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Write a helpful reply…" rows={3} aria-label="Comment" />
          <Button type="submit" disabled={busy || !comment.trim()}>
            {busy && <Spinner />} Reply
          </Button>
        </form>
      )}

      <div className="space-y-2">
        {post.comments.map((c) => (
          <Card key={c.id} className="gap-2 p-4">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {c.author.role === "teacher" && <GraduationCap className="size-3.5 text-emerald-600" />}
              <span className="font-semibold text-foreground">{c.author.name}</span> · {timeAgo(c.created_at)}
            </p>
            <p className="text-sm leading-relaxed whitespace-pre-line">{c.body}</p>
          </Card>
        ))}
      </div>
    </div>
  );
}
