import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus } from "lucide-react";
import { Field, FormAlert } from "@/components/form";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { api, qs } from "@/lib/api";
import type { AdminClass, AdminClassDetail, AdminLookups } from "@/types";
import { PageHeader, StatusBadge, Table, errorText, refreshAdmin, useLookups } from "./common";

export default function ClassesPage() {
  const lookups = useLookups();
  const [yearId, setYearId] = useState<string | null>(null);
  const [status, setStatus] = useState("active");
  const [creating, setCreating] = useState(false);
  const currentYear = lookups.data?.academic_years.find((y) => y.is_current)?.id ?? "";
  const year = yearId ?? currentYear;

  const { data, error, isPending, refetch } = useQuery({
    queryKey: ["admin", "classes", year, status],
    queryFn: () => api.get<AdminClass[]>(`/api/admin/classes${qs({ academic_year_id: year, status })}`),
    enabled: !lookups.isPending,
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Classes"
        description="Classes belong to an academic year. Archive old classes instead of deleting them; their history is kept."
        actions={
          <Button onClick={() => setCreating(true)} disabled={!lookups.data?.academic_years.length}>
            <Plus /> New class
          </Button>
        }
      />
      {lookups.data && lookups.data.academic_years.length === 0 && (
        <FormAlert tone="info">
          Create an academic year first on the <Link to="/admin/school" className="font-semibold underline">School</Link> page.
        </FormAlert>
      )}

      <div className="flex flex-wrap gap-3">
        <div className="w-48 space-y-1.5">
          <Label htmlFor="c-year">Academic year</Label>
          <Select id="c-year" value={year} onChange={(e) => setYearId(e.target.value)}>
            <option value="">All years</option>
            {lookups.data?.academic_years.map((y) => (
              <option key={y.id} value={y.id}>
                {y.name}
                {y.is_current ? " (current)" : ""}
              </option>
            ))}
          </Select>
        </div>
        <div className="w-40 space-y-1.5">
          <Label htmlFor="c-status">Status</Label>
          <Select id="c-status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </Select>
        </div>
      </div>

      {isPending || lookups.isPending ? (
        <PageLoader rows={0} />
      ) : error || !data ? (
        <ErrorState message={error?.message ?? "Could not load classes"} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyState emoji="🏫" title="No classes here" description="Create a class, then enrol students and assign teachers." />
      ) : (
        <Card className="gap-0 overflow-hidden p-0">
          <Table head={["Class", "Form", "Year", "Class teacher", "Students", "Subjects taught", "Status"]}>
            {data.map((c) => (
              <tr key={c.id}>
                <td className="px-4 py-3">
                  <Link to={`/admin/classes/${c.id}`} className="font-semibold text-primary hover:underline">
                    {c.name}
                  </Link>
                </td>
                <td className="px-4 py-3">Form {c.form}</td>
                <td className="px-4 py-3">
                  {c.academic_year.name} {c.academic_year.is_current && <Badge variant="muted">current</Badge>}
                </td>
                <td className="px-4 py-3">{c.class_teacher ? c.class_teacher.name : <span className="text-orange-700">Not assigned</span>}</td>
                <td className="px-4 py-3 tabular-nums">{c.student_count}</td>
                <td className="px-4 py-3 tabular-nums">{c.subject_count}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={c.status} />
                </td>
              </tr>
            ))}
          </Table>
        </Card>
      )}

      {lookups.data && <NewClassDialog open={creating} onOpenChange={setCreating} lookups={lookups.data} defaultYear={year || currentYear} />}
    </div>
  );
}

const schema = z.object({
  name: z.string().trim().min(1, "Enter a class name, e.g. 4 Bestari.").max(100),
  form: z.string().min(1, "Choose a form."),
  academic_year_id: z.string().min(1, "Choose an academic year."),
  class_teacher_id: z.string(),
});
type Values = z.infer<typeof schema>;

function NewClassDialog({ open, onOpenChange, lookups, defaultYear }: { open: boolean; onOpenChange: (o: boolean) => void; lookups: AdminLookups; defaultYear: string }) {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState, reset } = useForm<Values>({
    resolver: zodResolver(schema),
    values: { name: "", form: "", academic_year_id: defaultYear, class_teacher_id: "" },
  });

  const submit = async (v: Values) => {
    setError(null);
    try {
      const created = await api.post<AdminClassDetail>("/api/admin/classes", { ...v, form: Number(v.form), class_teacher_id: v.class_teacher_id || null });
      await refreshAdmin();
      reset();
      onOpenChange(false);
      navigate(`/admin/classes/${created.id}`);
    } catch (e) {
      setError(errorText(e, "Could not create the class"));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New class</DialogTitle>
          <DialogDescription>Class names must be unique within an academic year.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
          <Field id="n-name" label="Class name / code" error={formState.errors.name?.message}>
            <Input id="n-name" placeholder="4 Bestari" {...register("name")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="n-form" label="Form" error={formState.errors.form?.message}>
              <Select id="n-form" {...register("form")}>
                <option value="">—</option>
                {[1, 2, 3, 4, 5].map((f) => (
                  <option key={f} value={f}>
                    Form {f}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="n-year" label="Academic year" error={formState.errors.academic_year_id?.message}>
              <Select id="n-year" {...register("academic_year_id")}>
                <option value="">—</option>
                {lookups.academic_years.map((y) => (
                  <option key={y.id} value={y.id}>
                    {y.name}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field id="n-teacher" label="Class teacher (optional)">
            <Select id="n-teacher" {...register("class_teacher_id")}>
              <option value="">Assign later</option>
              {lookups.teachers
                .filter((t) => t.status === "active")
                .map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
            </Select>
          </Field>
          {error && <FormAlert>{error}</FormAlert>}
          <Button type="submit" className="w-full" disabled={formState.isSubmitting}>
            {formState.isSubmitting && <Spinner />} Create class
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
