import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { Bookmark, MessageCircle, PenSquare, Search } from "lucide-react";
import { EmptyState, ErrorState, Spinner } from "@/components/states";
import { VoteButton } from "@/components/vote-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";
import type { Post, SubjectSummary, TopicSummary } from "@/types";

interface Meta {
  teacher_categories: string[];
  can_post_student: boolean;
  can_post_teacher: boolean;
}

export default function CommunityPage({ space }: { space: "student" | "teacher" }) {
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState<"new" | "top">("new");
  const [saved, setSaved] = useState(false);
  const { data: meta } = useApi<Meta>("/api/community/meta");
  const { data: subjects } = useApi<SubjectSummary[]>("/api/subjects");
  const { data: topicData } = useApi<{ topics: TopicSummary[] }>(subjectId && space === "student" ? `/api/subjects/${subjectId}/topics` : null);
  const { data: posts, error, loading, reload } = useApi<Post[]>(
    `/api/community/posts${qs({ space, q: query, subject_id: subjectId, topic_id: topicId, category, sort, saved: saved ? "true" : "" })}`,
  );

  useEffect(() => setTopicId(""), [subjectId]);

  const canPost = space === "student" ? meta?.can_post_student : meta?.can_post_teacher;
  const base = user?.role === "student" ? "/community" : space === "teacher" ? "/teacher/community" : "/teacher/student-community";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{space === "student" ? "📚 Student Community" : "👨‍🏫 Teacher Community"}</h1>
          <p className="text-muted-foreground">
            {space === "student"
              ? `Ask questions and help classmates at ${user?.school ?? "your school"}.${user?.role !== "student" ? " (Read-only for teachers.)" : ""}`
              : "Share strategies, misconceptions and exam prep ideas with teachers everywhere."}
          </p>
        </div>
        {canPost && <NewPostDialog space={space} subjects={subjects ?? []} categories={meta?.teacher_categories ?? []} onCreated={reload} />}
      </div>

      <Card className="gap-3 p-4">
        <form
          className="flex gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            setQuery(search);
          }}
        >
          <div className="relative flex-1">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search posts…" className="pl-9" aria-label="Search posts" />
          </div>
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <div className="grid gap-2 sm:grid-cols-4">
          <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} aria-label="Filter by subject">
            <option value="">All subjects</option>
            {subjects?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          {space === "student" ? (
            <Select value={topicId} onChange={(e) => setTopicId(e.target.value)} disabled={!subjectId} aria-label="Filter by topic">
              <option value="">All topics</option>
              {topicData?.topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </Select>
          ) : (
            <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filter by category">
              <option value="">All categories</option>
              {meta?.teacher_categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </Select>
          )}
          <div className="flex gap-1 rounded-xl bg-muted p-1 sm:col-span-2 sm:w-fit">
            {(["new", "top"] as const).map((s) => (
              <button key={s} onClick={() => setSort(s)} className={`rounded-lg px-4 py-1.5 text-sm font-semibold capitalize ${sort === s ? "bg-card shadow-sm" : "text-muted-foreground"}`}>
                {s === "new" ? "Newest" : "Top"}
              </button>
            ))}
            <button onClick={() => setSaved(!saved)} aria-pressed={saved} className={`inline-flex items-center gap-1 rounded-lg px-4 py-1.5 text-sm font-semibold ${saved ? "bg-card shadow-sm" : "text-muted-foreground"}`}>
              <Bookmark className="size-3.5" /> Saved
            </button>
          </div>
        </div>
      </Card>

      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !posts && <Spinner className="mx-auto size-6" />}
      {posts && posts.length === 0 &&
        (saved ? (
          <EmptyState emoji="🔖" title="No saved posts" description="Save a post to find it here later." />
        ) : (
          <EmptyState emoji="💬" title="No posts yet" description={canPost ? "Be the first to start a discussion!" : "Nothing here yet."} />
        ))}

      <div className="space-y-3">
        {posts?.map((p) => (
          <Link key={p.id} to={`${base}/${p.id}`} className="block">
            <Card className="flex-row gap-3 p-4 transition-all hover:border-primary/30 hover:shadow-md">
              <VoteButton postId={p.id} score={p.score} myVote={p.my_vote} vertical disabled={!canPost || p.author.id === user?.id || p.status !== "visible"} />
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-1.5">
                  {p.status === "hidden" && <Badge variant="danger">Hidden by moderator</Badge>}
                  {p.bookmarked && <Bookmark className="size-3.5 fill-current text-primary" aria-label="Saved" />}
                  {p.subject && <Badge variant="secondary">{p.subject}</Badge>}
                  {p.topic && <Badge variant="muted">{p.topic}</Badge>}
                  {p.category && <Badge variant="outline">{p.category}</Badge>}
                </div>
                <p className="font-bold">{p.title}</p>
                <p className="line-clamp-2 text-sm text-muted-foreground">{p.body}</p>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>
                    Posted by <span className="font-semibold text-foreground">{p.author.name}</span> · {timeAgo(p.created_at)}
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <MessageCircle className="size-3.5" /> {p.comment_count} comments
                  </span>
                </div>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

function NewPostDialog({ space, subjects, categories, onCreated }: { space: "student" | "teacher"; subjects: SubjectSummary[]; categories: string[]; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: topicData } = useApi<{ topics: TopicSummary[] }>(subjectId && space === "student" ? `/api/subjects/${subjectId}/topics` : null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/community/posts", { space, title, body, subject_id: subjectId || null, topic_id: topicId || null, category: category || null });
      setOpen(false);
      setTitle("");
      setBody("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create post");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="gradient">
          <PenSquare /> New post
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{space === "student" ? "Ask your classmates" : "Start a discussion"}</DialogTitle>
          <DialogDescription>
            {space === "student"
              ? "Be kind and specific — share what you've tried. Links, email addresses and phone numbers aren't allowed."
              : "Visible to teachers from all schools. Don't include student names or results."}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} maxLength={300} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="body">Details</Label>
            <Textarea id="body" value={body} onChange={(e) => setBody(e.target.value)} required rows={5} />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)} aria-label="Subject">
              <option value="">Subject (optional)</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            {space === "student" ? (
              <Select value={topicId} onChange={(e) => setTopicId(e.target.value)} disabled={!subjectId} aria-label="Topic">
                <option value="">Topic (optional)</option>
                {topicData?.topics.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
            ) : (
              <Select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
                <option value="">Category (optional)</option>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </Select>
            )}
          </div>
          {error && <p className="text-sm text-orange-700">{error}</p>}
          <Button type="submit" variant="gradient" className="w-full" disabled={busy}>
            {busy && <Spinner />} Post
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
