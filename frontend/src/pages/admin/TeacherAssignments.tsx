import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { FormAlert } from "@/components/form";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import type { TeachingAssignment } from "@/types";
import { ConfirmButton, PageHeader, Table, errorText, refreshAdmin, useLookups } from "./common";

export default function TeacherAssignmentsPage() {
  const lookups = useLookups();
  const [filter, setFilter] = useState({ teacher_id: "", class_id: "", subject_id: "" });
  const [draft, setDraft] = useState({ teacher_id: "", subject_id: "", class_id: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, isPending, refetch } = useQuery({
    queryKey: ["admin", "teacher-assignments", filter],
    queryFn: () => api.get<TeachingAssignment[]>(`/api/admin/teacher-assignments${qs(filter)}`),
  });

  if (lookups.isPending) return <PageLoader rows={0} />;
  if (!lookups.data) return <ErrorState message={lookups.error?.message ?? "Could not load options"} onRetry={() => lookups.refetch()} />;
  const options = lookups.data;
  const activeTeachers = options.teachers.filter((t) => t.status === "active");

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/admin/teacher-assignments", draft);
      setDraft({ teacher_id: draft.teacher_id, subject_id: "", class_id: "" });
      await refreshAdmin();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const selects = (value: typeof filter, onChange: (key: keyof typeof filter, v: string) => void, anyLabel: boolean, idPrefix: string) => (
    <>
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-teacher`}>Teacher</Label>
        <Select id={`${idPrefix}-teacher`} value={value.teacher_id} onChange={(e) => onChange("teacher_id", e.target.value)}>
          <option value="">{anyLabel ? "Any teacher" : "Choose…"}</option>
          {(anyLabel ? options.teachers : activeTeachers).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
              {t.status !== "active" ? " (disabled)" : ""}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-subject`}>Subject</Label>
        <Select id={`${idPrefix}-subject`} value={value.subject_id} onChange={(e) => onChange("subject_id", e.target.value)}>
          <option value="">{anyLabel ? "Any subject" : "Choose…"}</option>
          {options.subjects.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={`${idPrefix}-class`}>Class</Label>
        <Select id={`${idPrefix}-class`} value={value.class_id} onChange={(e) => onChange("class_id", e.target.value)}>
          <option value="">{anyLabel ? "Any class" : "Choose…"}</option>
          {options.classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.academic_year})
            </option>
          ))}
        </Select>
      </div>
    </>
  );

  return (
    <div className="space-y-6">
      <PageHeader title="Teaching assignments" description="Which teacher teaches which subject to which class. A teacher's access to student records comes only from these and from being a class teacher." />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add an assignment</CardTitle>
          <CardDescription>A teacher can teach several subjects and classes. Class teachers are set on each class page.</CardDescription>
        </CardHeader>
        <div className="grid items-end gap-3 sm:grid-cols-4">
          {selects(draft, (k, v) => setDraft((d) => ({ ...d, [k]: v })), false, "a")}
          <Button onClick={add} disabled={busy || !draft.teacher_id || !draft.subject_id || !draft.class_id}>
            {busy ? <Spinner /> : <Plus />} Assign
          </Button>
        </div>
        {error && <FormAlert>{error}</FormAlert>}
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">{selects(filter, (k, v) => setFilter((f) => ({ ...f, [k]: v })), true, "f")}</div>

      {isPending ? (
        <PageLoader rows={0} />
      ) : loadError || !data ? (
        <ErrorState message={loadError?.message ?? "Could not load assignments"} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyState emoji="🧑‍🏫" title="No assignments match" description="Add one above." />
      ) : (
        <Card className="gap-0 overflow-hidden p-0">
          <Table head={["Teacher", "Subject", "Class", "Year", ""]}>
            {data.map((a) => (
              <tr key={a.id}>
                <td className="px-4 py-2.5">
                  <Link to={`/admin/users/${a.teacher.id}`} className="font-semibold text-primary hover:underline">
                    {a.teacher.name}
                  </Link>
                </td>
                <td className="px-4 py-2.5">{a.subject.name}</td>
                <td className="px-4 py-2.5">
                  <Link to={`/admin/classes/${a.class.id}`} className="hover:underline">
                    {a.class.name}
                  </Link>
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">{a.class.academic_year}</td>
                <td className="px-4 py-2.5 text-right">
                  <ConfirmButton
                    trigger={(open) => (
                      <Button variant="ghost" size="sm" onClick={open}>
                        <Trash2 /> Remove
                      </Button>
                    )}
                    title="Remove this assignment?"
                    description={`${a.teacher.name} will no longer see ${a.subject.name} records for ${a.class.name}.`}
                    confirmLabel="Remove"
                    destructive
                    onConfirm={async () => {
                      await api.del(`/api/admin/teacher-assignments/${a.id}`);
                      await refreshAdmin();
                    }}
                  />
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}
    </div>
  );
}
