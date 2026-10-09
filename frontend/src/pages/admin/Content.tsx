import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { EmptyState, ErrorState, PageLoader } from "@/components/states";
import { PageHeader, errorText, refreshAdmin } from "./common";

type SubjectRow = { id: string; code: string; name: string; status: "draft" | "published" | "archived"; forms: number[]; topic_count: number };
type TopicRow = { id: string; name: string; status: "draft" | "published" | "archived"; form: number | null; parent_id: string | null; objectives: { id: string; text: string }[] };

export default function ContentPage() {
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const subjects = useQuery({ queryKey: ["admin", "content-subjects"], queryFn: () => api.get<SubjectRow[]>("/api/admin/subjects") });
  const topics = useQuery({
    queryKey: ["admin", "content-topics", subjectId],
    queryFn: () => api.get<TopicRow[]>(`/api/admin/subjects/${subjectId}/topics`),
    enabled: !!subjectId,
  });

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      await refreshAdmin();
    } catch (e) {
      setError(errorText(e));
    }
  };

  if (subjects.isPending) return <PageLoader />;
  if (subjects.error || !subjects.data) return <ErrorState message={subjects.error?.message ?? "Could not load"} onRetry={() => subjects.refetch()} />;

  return (
    <div className="space-y-6">
      <PageHeader title="Content" description="Subjects, topics and lessons move from draft to published. Students only see published content." />
      {error && <p className="text-sm font-medium text-orange-700">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="gap-2">
          <CardHeader><CardTitle>Subjects</CardTitle></CardHeader>
          <NewSubject onCreate={(body) => run(() => api.post("/api/admin/subjects", body))} />
          <ul className="divide-y">
            {subjects.data.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-2 py-2">
                <button className="min-w-0 text-left" onClick={() => setSubjectId(s.id)}>
                  <p className="truncate font-semibold">{s.name}</p>
                  <p className="text-xs text-muted-foreground">{s.code} · {s.topic_count} topics{s.forms.length ? ` · Form ${s.forms.join(", ")}` : ""}</p>
                </button>
                <span className="flex items-center gap-2">
                  <Select aria-label={`${s.name} status`} value={s.status} onChange={(e) => run(() => api.post(`/api/admin/subjects/${s.id}/status`, { status: e.target.value }))}>
                    <option value="draft">Draft</option>
                    <option value="published">Published</option>
                    <option value="archived">Archived</option>
                  </Select>
                </span>
              </li>
            ))}
          </ul>
        </Card>
        <Card className="gap-2">
          <CardHeader><CardTitle>Topics</CardTitle></CardHeader>
          {!subjectId ? (
            <EmptyState emoji="📚" title="Choose a subject" />
          ) : topics.isPending ? (
            <PageLoader rows={0} />
          ) : (
            <>
              <NewTopic subjectId={subjectId} onCreate={(body) => run(() => api.post("/api/admin/topics", body))} />
              <ul className="divide-y">
                {(topics.data ?? []).map((t) => (
                  <li key={t.id} className="space-y-1 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{t.parent_id ? "↳ " : ""}{t.name}</p>
                      <Select aria-label={`${t.name} status`} value={t.status} onChange={(e) => run(() => api.post(`/api/admin/topics/${t.id}/status`, { status: e.target.value }))}>
                        <option value="draft">Draft</option>
                        <option value="published">Published</option>
                        <option value="archived">Archived</option>
                      </Select>
                    </div>
                    <ul className="text-sm text-muted-foreground">
                      {t.objectives.map((o) => <li key={o.id}>{o.text}</li>)}
                    </ul>
                    <ObjectiveForm onAdd={(text) => run(() => api.post(`/api/admin/topics/${t.id}/objectives`, { text }))} />
                  </li>
                ))}
              </ul>
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

function NewSubject({ onCreate }: { onCreate: (body: { code: string; name: string; forms: number[] }) => void }) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  return (
    <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); onCreate({ code, name, forms: [4] }); setCode(""); setName(""); }}>
      <Input aria-label="Subject code" placeholder="Code" value={code} onChange={(e) => setCode(e.target.value)} className="w-28" />
      <Input aria-label="Subject name" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} className="min-w-40 flex-1" />
      <Button type="submit" disabled={code.length < 2 || name.length < 2}>Add</Button>
    </form>
  );
}

function NewTopic({ subjectId, onCreate }: { subjectId: string; onCreate: (body: object) => void }) {
  const [name, setName] = useState("");
  return (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); onCreate({ subject_id: subjectId, name, form: 4 }); setName(""); }}>
      <Input aria-label="Topic name" placeholder="New topic" value={name} onChange={(e) => setName(e.target.value)} />
      <Button type="submit" disabled={!name.trim()}>Add</Button>
    </form>
  );
}

function ObjectiveForm({ onAdd }: { onAdd: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); onAdd(text); setText(""); }}>
      <Input aria-label="Learning objective" placeholder="Add a learning objective" value={text} onChange={(e) => setText(e.target.value)} />
      <Button type="submit" size="sm" variant="outline" disabled={!text.trim()}>Add</Button>
    </form>
  );
}
