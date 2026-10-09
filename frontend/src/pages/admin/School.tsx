import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CalendarPlus, CheckCircle2, Pencil, Plus, Save, Trash2 } from "lucide-react";
import { Field, FormAlert } from "@/components/form";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AcademicTerm, AcademicYear, SchoolProfile } from "@/types";
import { ConfirmButton, PageHeader, errorText, formatDate, refreshAdmin } from "./common";

export default function SchoolPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="School" description="School profile and academic calendar." />
      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="years">Academic years</TabsTrigger>
        </TabsList>
        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="years">
          <YearsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

const optional = (max: number) => z.string().trim().max(max);
const profileSchema = z.object({
  name: z.string().trim().min(2, "Enter the school name.").max(200),
  state: optional(100),
  address: optional(500),
  phone: optional(40),
  email: z.union([z.literal(""), z.string().trim().email("Enter a valid email address.")]),
  logo_url: z.union([z.literal(""), z.string().trim().url("Enter a full URL.").startsWith("https://", "Use an https:// address.")]),
  timezone: z.string(),
  description: optional(2000),
});
type ProfileValues = z.infer<typeof profileSchema>;

function ProfileTab() {
  const { refreshUser } = useAuth();
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, error: loadError, isPending, refetch } = useQuery({ queryKey: ["admin", "school"], queryFn: () => api.get<SchoolProfile>("/api/admin/school") });
  const { register, handleSubmit, formState, reset, watch } = useForm<ProfileValues>({ resolver: zodResolver(profileSchema) });

  useEffect(() => {
    if (data) {
      reset({
        name: data.name,
        state: data.state ?? "",
        address: data.address ?? "",
        phone: data.phone ?? "",
        email: data.email ?? "",
        logo_url: data.logo_url ?? "",
        timezone: data.timezone,
        description: data.description ?? "",
      });
    }
  }, [data, reset]);

  if (isPending) return <PageLoader rows={0} />;
  if (loadError || !data) return <ErrorState message={loadError?.message ?? "Could not load the school"} onRetry={() => refetch()} />;

  const save = async (v: ProfileValues) => {
    setSaved(false);
    setError(null);
    try {
      await api.put("/api/admin/school", v);
      await refreshAdmin();
      await refreshUser();
      setSaved(true);
    } catch (e) {
      setError(errorText(e, "Could not save"));
    }
  };

  const logo = watch("logo_url");

  return (
    <Card>
      <CardHeader>
        <CardTitle>School profile</CardTitle>
        <CardDescription>The name and logo appear in the navigation for everyone in your school.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(save)} noValidate className="grid gap-4 sm:grid-cols-2">
        <Field id="s-name" label="School name" error={formState.errors.name?.message}>
          <Input id="s-name" {...register("name")} />
        </Field>
        <Field id="s-state" label="State" error={formState.errors.state?.message}>
          <Input id="s-state" {...register("state")} />
        </Field>
        <div className="sm:col-span-2">
          <Field id="s-address" label="Address" error={formState.errors.address?.message}>
            <Textarea id="s-address" className="min-h-20" {...register("address")} />
          </Field>
        </div>
        <Field id="s-phone" label="Phone" error={formState.errors.phone?.message}>
          <Input id="s-phone" {...register("phone")} />
        </Field>
        <Field id="s-email" label="Office email" error={formState.errors.email?.message}>
          <Input id="s-email" type="email" {...register("email")} />
        </Field>
        <Field id="s-logo" label="Logo URL" error={formState.errors.logo_url?.message} hint="An https:// link to a square image. Uploading files arrives with content storage in Phase 3.">
          <div className="flex items-center gap-3">
            <Input id="s-logo" placeholder="https://" {...register("logo_url")} />
            {logo?.startsWith("https://") && <img src={logo} alt="" className="size-10 shrink-0 rounded-lg border object-contain" />}
          </div>
        </Field>
        <Field id="s-tz" label="Timezone">
          <Select id="s-tz" {...register("timezone")}>
            {data.timezones.map((tz) => (
              <option key={tz} value={tz}>
                {tz.replace("_", " ")}
              </option>
            ))}
          </Select>
        </Field>
        <div className="sm:col-span-2">
          <Field id="s-desc" label="Description (optional)" error={formState.errors.description?.message}>
            <Textarea id="s-desc" {...register("description")} />
          </Field>
        </div>
        <div className="space-y-2 sm:col-span-2">
          {error && <FormAlert>{error}</FormAlert>}
          {saved && !formState.isDirty && <FormAlert tone="success">School profile saved.</FormAlert>}
          <Button type="submit" disabled={formState.isSubmitting || !formState.isDirty}>
            {formState.isSubmitting ? <Spinner /> : <Save />} Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}

const rangeSchema = z
  .object({ name: z.string().trim().min(1, "Enter a name.").max(60), start_date: z.string().min(1, "Choose a date."), end_date: z.string().min(1, "Choose a date.") })
  .refine((v) => !v.start_date || !v.end_date || v.end_date > v.start_date, { message: "End date must be after the start date.", path: ["end_date"] });
type RangeValues = z.infer<typeof rangeSchema>;

function RangeDialog({
  title,
  description,
  initial,
  submitLabel,
  onSubmit,
  onClose,
}: {
  title: string;
  description?: string;
  initial: RangeValues;
  submitLabel: string;
  onSubmit: (v: RangeValues) => Promise<unknown>;
  onClose: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<RangeValues>({ resolver: zodResolver(rangeSchema), defaultValues: initial });
  const submit = async (v: RangeValues) => {
    setError(null);
    try {
      await onSubmit(v);
      onClose();
    } catch (e) {
      setError(errorText(e));
    }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        <form onSubmit={handleSubmit(submit)} noValidate className="space-y-4">
          <Field id="r-name" label="Name" error={formState.errors.name?.message}>
            <Input id="r-name" {...register("name")} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="r-start" label="Starts" error={formState.errors.start_date?.message}>
              <Input id="r-start" type="date" {...register("start_date")} />
            </Field>
            <Field id="r-end" label="Ends" error={formState.errors.end_date?.message}>
              <Input id="r-end" type="date" {...register("end_date")} />
            </Field>
          </div>
          {error && <FormAlert>{error}</FormAlert>}
          <Button type="submit" className="w-full" disabled={formState.isSubmitting}>
            {formState.isSubmitting && <Spinner />} {submitLabel}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

type Editing =
  | { kind: "new-year" }
  | { kind: "year"; year: AcademicYear }
  | { kind: "new-term"; year: AcademicYear }
  | { kind: "term"; year: AcademicYear; term: AcademicTerm }
  | null;

function YearsTab() {
  const [editing, setEditing] = useState<Editing>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { data, error, isPending, refetch } = useQuery({ queryKey: ["admin", "academic-years"], queryFn: () => api.get<AcademicYear[]>("/api/admin/academic-years") });

  if (isPending) return <PageLoader rows={0} />;
  if (error || !data) return <ErrorState message={error?.message ?? "Could not load academic years"} onRetry={() => refetch()} />;

  const done = async (text: string) => {
    await refreshAdmin();
    setNotice(text);
  };
  const nextYear = String(new Date().getFullYear() + (data.length ? 1 : 0));

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Classes belong to an academic year. Adding next year keeps this year's classes and records unchanged.</p>
        <Button onClick={() => setEditing({ kind: "new-year" })}>
          <CalendarPlus /> New academic year
        </Button>
      </div>
      {notice && <FormAlert tone="success">{notice}</FormAlert>}

      {data.length === 0 ? (
        <EmptyState emoji="🗓️" title="No academic years yet" description="Create the current academic year before adding classes." />
      ) : (
        data.map((y) => (
          <Card key={y.id} className="gap-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {y.name} {y.is_current && <Badge variant="success">Current</Badge>}
                </CardTitle>
                <CardDescription>
                  {formatDate(y.start_date)} – {formatDate(y.end_date)} · {y.class_count} class{y.class_count === 1 ? "" : "es"}
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                {!y.is_current && (
                  <ConfirmButton
                    trigger={(open) => (
                      <Button size="sm" variant="outline" onClick={open}>
                        <CheckCircle2 /> Make current
                      </Button>
                    )}
                    title={`Make ${y.name} the current academic year?`}
                    description="New enrolments and imports default to the current year. Existing classes and records are not changed."
                    confirmLabel="Make current"
                    onConfirm={async () => {
                      await api.post(`/api/admin/academic-years/${y.id}/set-current`);
                      await done(`${y.name} is now the current academic year.`);
                    }}
                  />
                )}
                <Button size="sm" variant="outline" onClick={() => setEditing({ kind: "year", year: y })}>
                  <Pencil /> Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditing({ kind: "new-term", year: y })}>
                  <Plus /> Add term
                </Button>
              </div>
            </div>
            {y.terms.length === 0 ? (
              <p className="text-sm text-muted-foreground">No terms yet.</p>
            ) : (
              <ul className="divide-y rounded-xl border text-sm">
                {y.terms.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 px-3 py-2">
                    <span>
                      <span className="font-semibold">{t.name}</span>{" "}
                      <span className="text-muted-foreground">
                        {formatDate(t.start_date)} – {formatDate(t.end_date)}
                      </span>
                    </span>
                    <span className="flex gap-1">
                      <Button size="sm" variant="ghost" onClick={() => setEditing({ kind: "term", year: y, term: t })} aria-label={`Edit ${t.name}`}>
                        <Pencil />
                      </Button>
                      <ConfirmButton
                        trigger={(open) => (
                          <Button size="sm" variant="ghost" onClick={open} aria-label={`Delete ${t.name}`}>
                            <Trash2 />
                          </Button>
                        )}
                        title={`Delete ${t.name}?`}
                        description="Terms do not hold student records yet, so this only removes the dates."
                        confirmLabel="Delete term"
                        destructive
                        onConfirm={async () => {
                          await api.del(`/api/admin/academic-terms/${t.id}`);
                          await done(`${t.name} deleted.`);
                        }}
                      />
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        ))
      )}

      {editing?.kind === "new-year" && (
        <RangeDialog
          title="New academic year"
          description="If there is no current year yet, this one becomes current."
          initial={{ name: nextYear, start_date: `${nextYear}-01-01`, end_date: `${nextYear}-12-31` }}
          submitLabel="Create year"
          onClose={() => setEditing(null)}
          onSubmit={async (v) => {
            await api.post("/api/admin/academic-years", v);
            await done(`Academic year ${v.name} created.`);
          }}
        />
      )}
      {editing?.kind === "year" && (
        <RangeDialog
          title={`Edit ${editing.year.name}`}
          description="Terms must stay inside the year's dates."
          initial={{ name: editing.year.name, start_date: editing.year.start_date, end_date: editing.year.end_date }}
          submitLabel="Save"
          onClose={() => setEditing(null)}
          onSubmit={async (v) => {
            await api.put(`/api/admin/academic-years/${editing.year.id}`, { ...v, is_current: editing.year.is_current });
            await done("Academic year saved.");
          }}
        />
      )}
      {editing?.kind === "new-term" && (
        <RangeDialog
          title={`Add a term to ${editing.year.name}`}
          description="Terms cannot overlap."
          initial={{ name: `Term ${editing.year.terms.length + 1}`, start_date: "", end_date: "" }}
          submitLabel="Add term"
          onClose={() => setEditing(null)}
          onSubmit={async (v) => {
            await api.post(`/api/admin/academic-years/${editing.year.id}/terms`, v);
            await done(`${v.name} added to ${editing.year.name}.`);
          }}
        />
      )}
      {editing?.kind === "term" && (
        <RangeDialog
          title={`Edit ${editing.term.name}`}
          initial={{ name: editing.term.name, start_date: editing.term.start_date, end_date: editing.term.end_date }}
          submitLabel="Save"
          onClose={() => setEditing(null)}
          onSubmit={async (v) => {
            await api.put(`/api/admin/academic-terms/${editing.term.id}`, v);
            await done("Term saved.");
          }}
        />
      )}
    </div>
  );
}
