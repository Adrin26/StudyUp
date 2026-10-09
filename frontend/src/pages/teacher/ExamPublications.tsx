import { useState, type FormEvent } from "react";
import { CalendarClock, Trash2 } from "lucide-react";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";

interface Publication {
  id: string;
  class_id: string;
  class_name: string | null;
  opens_at: string;
  closes_at: string;
  release_at: string;
  duration_minutes: number | null;
  attempts: number;
}

interface Results {
  summary: { students: number; submitted: number; average: number | null };
  exam: { total_marks: number };
  students: { student_id: string; name: string; status: "not_started" | "in_progress" | "submitted"; marks: number | null }[];
}

const STATUS_LABEL = { not_started: "Not started", in_progress: "In progress", submitted: "Submitted" } as const;
const fmt = (d: string) => new Date(d).toLocaleString("en-MY", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

export function ExamPublications({ examId }: { examId: string }) {
  const { data: pubs, reload } = useApi<Publication[]>(`/api/exams/${examId}/publications`);
  const [openId, setOpenId] = useState<string | null>(null);

  const unpublish = async (p: Publication) => {
    if (!confirm(`Remove this exam from ${p.class_name}?`)) return;
    await api.del(`/api/exams/publications/${p.id}`);
    reload();
  };

  return (
    <Card className="gap-3 print:hidden">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-bold">Online sittings</p>
          <p className="text-sm text-muted-foreground">Publish to a class you teach. Answers stay hidden from students until the release time.</p>
        </div>
        <PublishDialog examId={examId} onDone={reload} />
      </div>
      {pubs && pubs.length === 0 && <p className="text-sm text-muted-foreground">Not published to any class yet.</p>}
      {pubs?.map((p) => (
        <div key={p.id} className="space-y-2 rounded-xl border p-3">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-semibold">{p.class_name}</p>
            <Badge variant="muted">{p.attempts} started</Badge>
            <p className="flex-1 text-xs text-muted-foreground">
              {fmt(p.opens_at)} – {fmt(p.closes_at)}
              {p.duration_minutes ? ` · ${p.duration_minutes} min` : ""} · answers released {fmt(p.release_at)}
            </p>
            <Button size="sm" variant="outline" onClick={() => setOpenId(openId === p.id ? null : p.id)}>
              {openId === p.id ? "Hide results" : "Results"}
            </Button>
            {p.attempts === 0 && (
              <Button size="sm" variant="ghost" onClick={() => unpublish(p)} aria-label={`Remove from ${p.class_name}`}>
                <Trash2 />
              </Button>
            )}
          </div>
          {openId === p.id && <ResultsTable publicationId={p.id} />}
        </div>
      ))}
    </Card>
  );
}

function ResultsTable({ publicationId }: { publicationId: string }) {
  const { data, error } = useApi<Results>(`/api/exams/publications/${publicationId}/results`);
  if (error) return <p className="text-sm text-orange-700">{error}</p>;
  if (!data) return <Spinner />;
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {data.summary.submitted} of {data.summary.students} submitted
        {data.summary.average != null && ` · average ${data.summary.average} / ${data.exam.total_marks}`}
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-muted-foreground">
            <th className="py-1 font-semibold">Student</th>
            <th className="py-1 font-semibold">Status</th>
            <th className="py-1 text-right font-semibold">Marks</th>
          </tr>
        </thead>
        <tbody>
          {data.students.map((s) => (
            <tr key={s.student_id} className="border-t">
              <td className="py-1.5">{s.name}</td>
              <td className="py-1.5">{STATUS_LABEL[s.status]}</td>
              <td className="py-1.5 text-right font-semibold">{s.marks != null ? `${s.marks} / ${data.exam.total_marks}` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PublishDialog({ examId, onDone }: { examId: string; onDone: () => void }) {
  const { data: classes } = useApi<{ id: string; name: string }[]>("/api/teachers/classes");
  const [open, setOpen] = useState(false);
  const [classId, setClassId] = useState("");
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [releaseAt, setReleaseAt] = useState("");
  const [duration, setDuration] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/exams/${examId}/publish`, {
        class_id: classId,
        opens_at: new Date(opensAt).toISOString(),
        closes_at: new Date(closesAt).toISOString(),
        release_at: new Date(releaseAt).toISOString(),
        duration_minutes: duration ? Number(duration) : null,
      });
      setOpen(false);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not publish");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="gradient">
          <CalendarClock /> Publish to class
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Publish to a class</DialogTitle>
          <DialogDescription>Students in the class sit the exam online during the window. Publishing again to the same class updates the schedule until someone starts.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="p-class">Class</Label>
            <Select id="p-class" value={classId} onChange={(e) => setClassId(e.target.value)} required>
              <option value="">Choose a class</option>
              {classes?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="p-opens">Opens</Label>
              <Input id="p-opens" type="datetime-local" value={opensAt} onChange={(e) => setOpensAt(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-closes">Closes</Label>
              <Input id="p-closes" type="datetime-local" value={closesAt} onChange={(e) => setClosesAt(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-release">Release answers</Label>
              <Input id="p-release" type="datetime-local" value={releaseAt} onChange={(e) => setReleaseAt(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-duration">Time limit (minutes)</Label>
              <Input id="p-duration" type="number" min={5} max={300} value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="None" />
            </div>
          </div>
          {error && <p className="text-sm text-orange-700">{error}</p>}
          <Button type="submit" variant="gradient" className="w-full" disabled={busy}>
            {busy && <Spinner />} Publish
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
