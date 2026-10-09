import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";

interface CalendarItem {
  id: string;
  source: "school" | "term" | "assignment" | "exam";
  kind: string;
  title: string;
  description: string | null;
  audience: "all" | "teachers" | "students";
  start_date: string;
  end_date: string;
  link: string | null;
  editable: boolean;
}

const KIND_STYLE: Record<string, { label: string; variant: "secondary" | "outline" | "muted" | "success" | "warning" | "danger" }> = {
  event: { label: "Event", variant: "secondary" },
  holiday: { label: "Holiday", variant: "success" },
  exam: { label: "Exam", variant: "danger" },
  meeting: { label: "Meeting", variant: "outline" },
  deadline: { label: "Deadline", variant: "warning" },
  term: { label: "Term", variant: "muted" },
};
const AUDIENCE_LABEL = { all: "Everyone", teachers: "Teachers", students: "Students" } as const;

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const parse = (s: string) => new Date(`${s}T00:00:00`);
const dayLabel = (s: string) => parse(s).toLocaleDateString("en-MY", { weekday: "short", day: "numeric", month: "short" });

export default function CalendarPage() {
  const { user } = useAuth();
  const [month, setMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [editing, setEditing] = useState<CalendarItem | "new" | null>(null);
  const start = iso(month);
  const end = iso(new Date(month.getFullYear(), month.getMonth() + 1, 0));
  const { data, error, loading, reload } = useApi<CalendarItem[]>(`/api/calendar${qs({ start, end })}`);
  const isAdmin = user?.role === "admin";

  const shift = (n: number) => setMonth(new Date(month.getFullYear(), month.getMonth() + n, 1));
  const remove = async (item: CalendarItem) => {
    if (!confirm(`Delete "${item.title}"?`)) return;
    await api.del(`/api/admin/calendar/${item.id}`);
    reload();
  };

  const terms = data?.filter((i) => i.source === "term") ?? [];
  const dated = data?.filter((i) => i.source !== "term") ?? [];
  const byDay = new Map<string, CalendarItem[]>();
  for (const item of dated) {
    const key = item.start_date < start ? start : item.start_date;
    byDay.set(key, [...(byDay.get(key) ?? []), item]);
  }
  const days = [...byDay.keys()].sort();

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight">School calendar</h1>
          <p className="text-muted-foreground">
            {user?.role === "student" ? "School events, terms, your exams and assignment deadlines." : user?.role === "teacher" ? "School events, terms, and your exams and assignment deadlines." : "School events and terms."}
          </p>
        </div>
        {isAdmin && (
          <Button variant="gradient" onClick={() => setEditing("new")}>
            <Plus /> Add event
          </Button>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={() => shift(-1)} aria-label="Previous month">
          <ChevronLeft />
        </Button>
        <p className="min-w-40 text-center font-bold">{month.toLocaleDateString("en-MY", { month: "long", year: "numeric" })}</p>
        <Button variant="outline" size="sm" onClick={() => shift(1)} aria-label="Next month">
          <ChevronRight />
        </Button>
      </div>

      {terms.length > 0 && (
        <p className="text-sm text-muted-foreground">
          {terms.map((t) => `${t.title}: ${dayLabel(t.start_date)} – ${dayLabel(t.end_date)}`).join(" · ")}
        </p>
      )}

      {loading && !data && <PageLoader rows={2} />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {data && days.length === 0 && <EmptyState emoji="📅" title="Nothing scheduled this month" />}

      <div className="space-y-4">
        {days.map((day) => (
          <section key={day} className="space-y-2">
            <h2 className="text-sm font-bold text-muted-foreground">{dayLabel(day)}</h2>
            {byDay.get(day)!.map((item) => {
              const style = KIND_STYLE[item.kind] ?? KIND_STYLE.event;
              const body = (
                <Card className="flex-row items-start gap-3 p-4">
                  <Badge variant={style.variant}>{style.label}</Badge>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{item.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.end_date !== item.start_date ? `${dayLabel(item.start_date)} – ${dayLabel(item.end_date)}` : dayLabel(item.start_date)}
                      {item.source === "school" && item.audience !== "all" && ` · ${AUDIENCE_LABEL[item.audience]}`}
                    </p>
                    {item.description && <p className="mt-1 text-sm whitespace-pre-line text-muted-foreground">{item.description}</p>}
                  </div>
                  {item.editable && (
                    <div className="flex gap-1">
                      <Button variant="ghost" size="sm" onClick={() => setEditing(item)} aria-label={`Edit ${item.title}`}>
                        <Pencil />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => remove(item)} aria-label={`Delete ${item.title}`}>
                        <Trash2 />
                      </Button>
                    </div>
                  )}
                </Card>
              );
              return item.link ? (
                <Link key={`${item.source}-${item.id}`} to={item.link} className="block">
                  {body}
                </Link>
              ) : (
                <div key={`${item.source}-${item.id}`}>{body}</div>
              );
            })}
          </section>
        ))}
      </div>

      {isAdmin && editing && (
        <EventDialog
          item={editing === "new" ? null : editing}
          defaultDate={start}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function EventDialog({ item, defaultDate, onClose, onSaved }: { item: CalendarItem | null; defaultDate: string; onClose: () => void; onSaved: () => void }) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [description, setDescription] = useState(item?.description ?? "");
  const [kind, setKind] = useState(item?.kind ?? "event");
  const [audience, setAudience] = useState<string>(item?.audience ?? "all");
  const [startDate, setStartDate] = useState(item?.start_date ?? defaultDate);
  const [endDate, setEndDate] = useState(item?.end_date ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body = { title, description: description || null, kind, audience, start_date: startDate, end_date: endDate || null };
    try {
      if (item) await api.patch(`/api/admin/calendar/${item.id}`, body);
      else await api.post("/api/admin/calendar", body);
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the event");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{item ? "Edit event" : "Add a school event"}</DialogTitle>
          <DialogDescription>Shown on the calendar of everyone in the chosen audience at your school.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="e-title">Title</Label>
            <Input id="e-title" value={title} onChange={(e) => setTitle(e.target.value)} required minLength={2} maxLength={200} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="e-kind">Type</Label>
              <Select id="e-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
                {["event", "holiday", "exam", "meeting", "deadline"].map((k) => (
                  <option key={k} value={k}>
                    {KIND_STYLE[k].label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="e-audience">Audience</Label>
              <Select id="e-audience" value={audience} onChange={(e) => setAudience(e.target.value)}>
                {Object.entries(AUDIENCE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="e-start">Starts</Label>
              <Input id="e-start" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="e-end">Ends (optional)</Label>
              <Input id="e-end" type="date" value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="e-desc">Details (optional)</Label>
            <Textarea id="e-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3} maxLength={2000} />
          </div>
          {error && <p className="text-sm text-orange-700">{error}</p>}
          <Button type="submit" variant="gradient" className="w-full" disabled={busy}>
            {busy && <Spinner />} Save
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
