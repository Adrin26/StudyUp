import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Archive, ArchiveRestore, ArrowRightLeft, Plus, Save, Trash2, UserMinus, UserPlus } from "lucide-react";
import { FormAlert } from "@/components/form";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import type { AdminClassDetail, AdminLookups } from "@/types";
import { ConfirmButton, PageHeader, StatusBadge, Table, errorText, formatDate, refreshAdmin, useLookups } from "./common";

type Notice = { tone: "success" | "error"; text: string } | null;

export default function ClassDetailPage() {
  const { classId = "" } = useParams();
  const lookups = useLookups();
  const [notice, setNotice] = useState<Notice>(null);
  const { data: klass, error, isPending, refetch } = useQuery({
    queryKey: ["admin", "class", classId],
    queryFn: () => api.get<AdminClassDetail>(`/api/admin/classes/${classId}`),
  });

  if (isPending || lookups.isPending) return <PageLoader rows={0} />;
  if (error || !klass || !lookups.data) return <ErrorState message={error?.message ?? "Could not load this class"} onRetry={() => refetch()} />;
  const active = klass.status === "active";

  const setStatus = async (action: "archive" | "restore") => {
    await api.post(`/api/admin/classes/${klass.id}/${action}`);
    await refreshAdmin();
    setNotice({ tone: "success", text: action === "archive" ? "Class archived. Its roster history is kept." : "Class restored." });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={klass.name}
        back={{ to: "/admin/classes", label: "Classes" }}
        description={
          <span className="flex flex-wrap items-center gap-2">
            Form {klass.form} · {klass.academic_year.name}
            {klass.academic_year.is_current && <Badge variant="muted">current year</Badge>}
            <StatusBadge status={klass.status} />
          </span>
        }
        actions={
          active ? (
            <ConfirmButton
              trigger={(open) => (
                <Button variant="outline" onClick={open}>
                  <Archive /> Archive
                </Button>
              )}
              title={`Archive ${klass.name}?`}
              description="The roster and history are kept, but teachers lose access to students through this class and no one can be enrolled. You can restore it later."
              confirmLabel="Archive class"
              destructive
              onConfirm={() => setStatus("archive")}
            />
          ) : (
            <Button variant="outline" onClick={() => setStatus("restore").catch((e) => setNotice({ tone: "error", text: errorText(e) }))}>
              <ArchiveRestore /> Restore
            </Button>
          )
        }
      />
      {notice && <FormAlert tone={notice.tone}>{notice.text}</FormAlert>}
      {!active && <FormAlert tone="info">This class is archived. Restore it to make changes.</FormAlert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <RosterCard klass={klass} lookups={lookups.data} onNotice={setNotice} />
        </div>
        <div className="space-y-4">
          {active && <DetailsCard klass={klass} lookups={lookups.data} onNotice={setNotice} />}
          <TeachingCard klass={klass} lookups={lookups.data} />
        </div>
      </div>
    </div>
  );
}

function DetailsCard({ klass, lookups, onNotice }: { klass: AdminClassDetail; lookups: AdminLookups; onNotice: (n: Notice) => void }) {
  const [name, setName] = useState(klass.name);
  const [form, setForm] = useState(String(klass.form));
  const [teacher, setTeacher] = useState(klass.class_teacher?.id ?? "");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setName(klass.name);
    setForm(String(klass.form));
    setTeacher(klass.class_teacher?.id ?? "");
  }, [klass]);
  const dirty = name.trim() !== klass.name || form !== String(klass.form) || teacher !== (klass.class_teacher?.id ?? "");

  const save = async () => {
    setBusy(true);
    try {
      await api.patch(`/api/admin/classes/${klass.id}`, { name: name.trim(), form: Number(form), class_teacher_id: teacher || null });
      await refreshAdmin();
      onNotice({ tone: "success", text: "Class details saved." });
    } catch (e) {
      onNotice({ tone: "error", text: errorText(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="gap-3">
      <CardTitle className="text-base">Details</CardTitle>
      <div className="space-y-1.5">
        <Label htmlFor="d-name">Name / code</Label>
        <Input id="d-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="d-form">Form</Label>
        <Select id="d-form" value={form} onChange={(e) => setForm(e.target.value)}>
          {[1, 2, 3, 4, 5].map((f) => (
            <option key={f} value={f}>
              Form {f}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="d-teacher">Class teacher</Label>
        <Select id="d-teacher" value={teacher} onChange={(e) => setTeacher(e.target.value)}>
          <option value="">None</option>
          {lookups.teachers
            .filter((t) => t.status === "active" || t.id === klass.class_teacher?.id)
            .map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
        </Select>
        <p className="text-xs text-muted-foreground">The class teacher sees every subject for students in this class.</p>
      </div>
      <Button className="w-fit" onClick={save} disabled={busy || !dirty || !name.trim()}>
        {busy ? <Spinner /> : <Save />} Save
      </Button>
    </Card>
  );
}

function RosterCard({ klass, lookups, onNotice }: { klass: AdminClassDetail; lookups: AdminLookups; onNotice: (n: Notice) => void }) {
  const active = klass.status === "active";
  const [adding, setAdding] = useState(false);
  const [moving, setMoving] = useState<{ id: string; name: string } | null>(null);
  const sameYear = lookups.classes.filter((c) => c.academic_year_id === klass.academic_year.id && c.id !== klass.id);

  const withdraw = async (id: string, name: string) => {
    await api.del(`/api/admin/classes/${klass.id}/students/${id}`);
    await refreshAdmin();
    onNotice({ tone: "success", text: `${name} was withdrawn from ${klass.name}.` });
  };

  return (
    <>
      <Card className="gap-0 overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <div>
            <CardTitle>Students ({klass.students.length})</CardTitle>
            <CardDescription>Currently enrolled.</CardDescription>
          </div>
          {active && (
            <Button onClick={() => setAdding(true)}>
              <UserPlus /> Enrol students
            </Button>
          )}
        </div>
        {klass.students.length === 0 ? (
          <div className="px-5 pb-5">
            <EmptyState emoji="🧑‍🎓" title="No students enrolled" description={active ? "Use Enrol students to add them." : undefined} />
          </div>
        ) : (
          <Table head={["Name", "Student ID", "Enrolled", ""]}>
            {klass.students.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2.5">
                  <Link to={`/admin/users/${s.id}`} className="font-semibold text-primary hover:underline">
                    {s.full_name}
                  </Link>
                  {s.status === "disabled" && <Badge variant="danger" className="ml-2">Disabled</Badge>}
                </td>
                <td className="px-4 py-2.5">{s.student_number ?? "—"}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{formatDate(s.enrolled_at)}</td>
                <td className="px-4 py-2.5 text-right whitespace-nowrap">
                  {active && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => setMoving({ id: s.id, name: s.full_name })} disabled={sameYear.length === 0} title={sameYear.length === 0 ? "No other class in this academic year" : undefined}>
                        <ArrowRightLeft /> Transfer
                      </Button>
                      <ConfirmButton
                        trigger={(open) => (
                          <Button variant="ghost" size="sm" onClick={open}>
                            <UserMinus /> Withdraw
                          </Button>
                        )}
                        title={`Withdraw ${s.full_name}?`}
                        description={`They leave ${klass.name}. The enrolment stays in their history and their learning records are kept.`}
                        confirmLabel="Withdraw"
                        destructive
                        onConfirm={() => withdraw(s.id, s.full_name)}
                      />
                    </>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        )}
      </Card>

      {klass.former_students.length > 0 && (
        <Card className="gap-0 overflow-hidden p-0">
          <div className="p-5 pb-3">
            <CardTitle className="text-base">Former students</CardTitle>
          </div>
          <Table head={["Name", "Left because", "Enrolled", "Left"]}>
            {klass.former_students.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-2.5">
                  <Link to={`/admin/users/${s.id}`} className="font-medium hover:underline">
                    {s.full_name}
                  </Link>
                </td>
                <td className="px-4 py-2.5 capitalize">{s.status}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{formatDate(s.enrolled_at)}</td>
                <td className="px-4 py-2.5 text-muted-foreground">{formatDate(s.left_at)}</td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      {adding && <EnrolDialog klass={klass} onClose={() => setAdding(false)} onNotice={onNotice} />}
      {moving && (
        <TransferDialog
          klass={klass}
          student={moving}
          targets={sameYear}
          onClose={() => setMoving(null)}
          onDone={(to) => onNotice({ tone: "success", text: `${moving.name} moved to ${to}. The move is recorded in their enrolment history.` })}
        />
      )}
    </>
  );
}

function EnrolDialog({ klass, onClose, onNotice }: { klass: AdminClassDetail; onClose: () => void; onNotice: (n: Notice) => void }) {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, isPending } = useQuery({
    queryKey: ["admin", "eligible", klass.id, query],
    queryFn: () => api.get<{ id: string; full_name: string; student_number: string | null; form: number | null }[]>(`/api/admin/classes/${klass.id}/eligible-students${qs({ q: query })}`),
  });

  const enrol = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ enrolled: string[]; already_enrolled: string[]; failed: { id: string; reason: string }[] }>(`/api/admin/classes/${klass.id}/students`, { student_ids: selected });
      await refreshAdmin();
      if (res.failed.length) {
        setError(res.failed.map((f) => f.reason).join(" "));
        setSelected([]);
      } else {
        onNotice({ tone: "success", text: `${res.enrolled.length} student${res.enrolled.length === 1 ? "" : "s"} enrolled in ${klass.name}.` });
        onClose();
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Enrol students in {klass.name}</DialogTitle>
          <DialogDescription>Showing active students who are not in any class for {klass.academic_year.name}. To move a student from another class, use Transfer there.</DialogDescription>
        </DialogHeader>
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(search.trim());
          }}
        >
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or student ID" aria-label="Search students" />
          <Button type="submit" variant="secondary">
            Search
          </Button>
        </form>
        <div className="max-h-72 space-y-1 overflow-y-auto rounded-xl border p-2">
          {isPending ? (
            <div className="flex justify-center p-6">
              <Spinner className="size-5" />
            </div>
          ) : !data?.length ? (
            <p className="p-4 text-center text-sm text-muted-foreground">No unplaced students{query ? " match that search" : ""}.</p>
          ) : (
            data.map((s) => (
              <label key={s.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted">
                <Checkbox checked={selected.includes(s.id)} onCheckedChange={() => setSelected((x) => (x.includes(s.id) ? x.filter((i) => i !== s.id) : [...x, s.id]))} />
                <span className="flex-1 text-sm font-medium">{s.full_name}</span>
                <span className="text-xs text-muted-foreground">
                  {s.student_number ?? ""} {s.form ? `· Form ${s.form}` : ""}
                </span>
              </label>
            ))
          )}
        </div>
        {error && <FormAlert>{error}</FormAlert>}
        <Button onClick={enrol} disabled={busy || selected.length === 0}>
          {busy ? <Spinner /> : <UserPlus />} Enrol {selected.length} student{selected.length === 1 ? "" : "s"}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function TransferDialog({
  klass,
  student,
  targets,
  onClose,
  onDone,
}: {
  klass: AdminClassDetail;
  student: { id: string; name: string };
  targets: AdminLookups["classes"];
  onClose: () => void;
  onDone: (to: string) => void;
}) {
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const move = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/api/admin/classes/${klass.id}/students/${student.id}/transfer`, { to_class_id: to });
      await refreshAdmin();
      onDone(targets.find((t) => t.id === to)?.name ?? "the new class");
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Transfer {student.name}</DialogTitle>
          <DialogDescription>Move to another class in {klass.academic_year.name}. The time in {klass.name} stays in their history.</DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="t-to">New class</Label>
          <Select id="t-to" value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">Choose a class…</option>
            {targets.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
        {error && <FormAlert>{error}</FormAlert>}
        <Button onClick={move} disabled={busy || !to}>
          {busy ? <Spinner /> : <ArrowRightLeft />} Transfer
        </Button>
      </DialogContent>
    </Dialog>
  );
}

function TeachingCard({ klass, lookups }: { klass: AdminClassDetail; lookups: AdminLookups }) {
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = klass.status === "active";

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/admin/teacher-assignments", { teacher_id: teacherId, subject_id: subjectId, class_id: klass.id });
      setSubjectId("");
      setTeacherId("");
      await refreshAdmin();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="gap-3">
      <CardHeader>
        <CardTitle className="text-base">Subject teachers</CardTitle>
        <CardDescription>Each teacher sees only their subject for this class.</CardDescription>
      </CardHeader>
      {klass.teaching.length === 0 ? (
        <p className="text-sm text-orange-700">No subjects assigned yet.</p>
      ) : (
        <ul className="divide-y rounded-xl border text-sm">
          {klass.teaching.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 px-3 py-2">
              <span>
                <span className="font-semibold">{t.subject.name}</span>
                <Link to={`/admin/users/${t.teacher.id}`} className="block text-xs text-primary hover:underline">
                  {t.teacher.name}
                </Link>
              </span>
              {active && (
                <ConfirmButton
                  trigger={(open) => (
                    <Button variant="ghost" size="sm" onClick={open} aria-label={`Remove ${t.teacher.name} from ${t.subject.name}`}>
                      <Trash2 />
                    </Button>
                  )}
                  title="Remove this assignment?"
                  description={`${t.teacher.name} will no longer see ${t.subject.name} records for ${klass.name}.`}
                  confirmLabel="Remove"
                  destructive
                  onConfirm={async () => {
                    await api.del(`/api/admin/teacher-assignments/${t.id}`);
                    await refreshAdmin();
                  }}
                />
              )}
            </li>
          ))}
        </ul>
      )}
      {active && (
        <div className="space-y-2">
          <Select aria-label="Subject" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            <option value="">Subject…</option>
            {lookups.subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Select aria-label="Teacher" value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="">Teacher…</option>
            {lookups.teachers
              .filter((t) => t.status === "active")
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
          </Select>
          <Button size="sm" onClick={add} disabled={busy || !subjectId || !teacherId}>
            {busy ? <Spinner /> : <Plus />} Assign teacher
          </Button>
          {error && <FormAlert>{error}</FormAlert>}
        </div>
      )}
    </Card>
  );
}
