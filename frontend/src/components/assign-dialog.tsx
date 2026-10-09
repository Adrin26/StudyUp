import { useState, type FormEvent, type ReactNode } from "react";
import { CheckCircle2 } from "lucide-react";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { api } from "@/lib/api";

export function AssignDialog({
  trigger,
  subjectId,
  topicId,
  topicName,
  students,
  examId,
  onDone,
}: {
  trigger: ReactNode;
  subjectId: string;
  topicId?: string;
  topicName?: string;
  students: { id: string; name: string; mastery?: number }[];
  examId?: string;
  onDone?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(topicName ? `${topicName} practice` : "Practice set");
  const [selected, setSelected] = useState<string[]>(students.map((s) => s.id));
  const [count, setCount] = useState(8);
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ student_count: number; question_count: number }>("/api/teachers/assignments", {
        title,
        subject_id: subjectId,
        topic_id: topicId ?? null,
        student_ids: selected,
        num_questions: count,
        due_date: due || null,
        exam_id: examId ?? null,
      });
      setDone(`Assigned ${res.question_count} questions to ${res.student_count} students. It now appears on their dashboards.`);
      onDone?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create assignment");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) setDone(null);
      }}
    >
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Assign a practice set</DialogTitle>
          <DialogDescription>Questions are picked from the question bank. Students see it on their dashboard.</DialogDescription>
        </DialogHeader>
        {done ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <CheckCircle2 className="size-12 text-emerald-500" />
            <p className="font-semibold">{done}</p>
            <Button onClick={() => setOpen(false)}>Close</Button>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="a-title">Title</Label>
              <Input id="a-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {!examId && (
                <div className="space-y-1.5">
                  <Label>Questions</Label>
                  <Select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                    {[5, 8, 10, 15, 20].map((n) => (
                      <option key={n}>{n}</option>
                    ))}
                  </Select>
                </div>
              )}
              <div className="space-y-1.5">
                <Label htmlFor="a-due">Due date</Label>
                <Input id="a-due" type="date" value={due} onChange={(e) => setDue(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Students ({selected.length})</Label>
              <div className="max-h-52 space-y-1 overflow-y-auto rounded-xl border p-2">
                {students.map((s) => (
                  <label key={s.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted">
                    <Checkbox checked={selected.includes(s.id)} onCheckedChange={() => setSelected((x) => (x.includes(s.id) ? x.filter((i) => i !== s.id) : [...x, s.id]))} />
                    <span className="flex-1 text-sm font-medium">{s.name}</span>
                    {s.mastery != null && <span className="text-xs font-bold text-orange-600">{Math.round(s.mastery)}%</span>}
                  </label>
                ))}
              </div>
            </div>
            {error && <p className="text-sm text-orange-700">{error}</p>}
            <Button type="submit" variant="gradient" className="w-full" disabled={busy || selected.length === 0}>
              {busy && <Spinner />} Assign to {selected.length} student{selected.length === 1 ? "" : "s"}
            </Button>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
