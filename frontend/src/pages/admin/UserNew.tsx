import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus } from "lucide-react";
import { Field, FormAlert } from "@/components/form";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminUserDetail, LinkResult } from "@/types";
import { PageHeader, errorText, refreshAdmin, useLookups } from "./common";
import { AssignmentRows, SubjectPicker, identityFields, type PairDraft } from "./user-fields";

const schema = z.object({
  ...identityFields,
  class_id: z.string(),
  status: z.enum(["active", "disabled"]),
  send_invite: z.boolean(),
});
type Values = z.infer<typeof schema>;

export default function UserNewPage() {
  const [params] = useSearchParams();
  const role = params.get("role") === "teacher" ? "teacher" : "student";
  const navigate = useNavigate();
  const { usesSupabase } = useAuth();
  const lookups = useLookups();
  const [subjectIds, setSubjectIds] = useState<string[]>([]);
  const [pairs, setPairs] = useState<PairDraft[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState, watch, setValue } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: "", email: "", username: "", id_number: "", form: "", department: "", class_id: "", status: "active", send_invite: true },
  });
  const isStudent = role === "student";
  const label = isStudent ? "student" : "teacher";

  if (lookups.isPending) return <PageLoader rows={0} />;
  if (lookups.error || !lookups.data) return <ErrorState message={lookups.error?.message ?? "Could not load options"} onRetry={() => lookups.refetch()} />;
  const options = lookups.data;

  const submit = async (v: Values) => {
    setError(null);
    const incomplete = pairs.some((p) => !p.subject_id || !p.class_id);
    if (incomplete) {
      setError("Choose both a subject and a class for each teaching row, or remove the empty row.");
      return;
    }
    try {
      const res = await api.post<{ user: AdminUserDetail; invitation: LinkResult | null }>("/api/admin/users", {
        role,
        full_name: v.full_name,
        email: v.email,
        username: v.username || null,
        status: v.status,
        send_invite: v.send_invite,
        ...(isStudent
          ? { student_number: v.id_number, form: v.form ? Number(v.form) : null, class_id: v.class_id || null, subject_ids: subjectIds }
          : { staff_number: v.id_number, department: v.department || null, assignments: pairs }),
      });
      await refreshAdmin();
      const notice = res.invitation ? `Account created. ${res.invitation.message}` : "Account created. No set-password link was sent; use “Send set-password link” when they are ready.";
      navigate(`/admin/users/${res.user.id}`, { state: { notice, delivered: res.invitation?.delivered ?? true } });
    } catch (e) {
      setError(errorText(e, "Could not create the account"));
    }
  };

  const status = watch("status");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title={`Add ${label}`} back={{ to: "/admin/users", label: "Users" }} description="The user chooses their own password through a single-use link. You never see or set it." />
      {usesSupabase && <FormAlert tone="info">Account creation from MINDA is not available while sign-in is handled by Supabase. Invite users from the Supabase dashboard.</FormAlert>}

      <form onSubmit={handleSubmit(submit)} noValidate className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Account details</CardTitle>
          </CardHeader>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="full_name" label="Full name" error={formState.errors.full_name?.message}>
              <Input id="full_name" autoComplete="off" {...register("full_name")} />
            </Field>
            <Field id="id_number" label={isStudent ? "Student ID" : "Staff ID"} error={formState.errors.id_number?.message} hint="Unique within your school.">
              <Input id="id_number" autoComplete="off" {...register("id_number")} />
            </Field>
            <Field id="email" label="Email" error={formState.errors.email?.message}>
              <Input id="email" type="email" autoComplete="off" {...register("email")} />
            </Field>
            <Field id="username" label="Username (optional)" error={formState.errors.username?.message} hint="Left blank, it is taken from the email.">
              <Input id="username" autoComplete="off" {...register("username")} />
            </Field>
            {isStudent ? (
              <Field id="form" label="Form (optional)" hint="Taken from the class if left blank.">
                <Select id="form" {...register("form")}>
                  <option value="">—</option>
                  {[1, 2, 3, 4, 5].map((f) => (
                    <option key={f} value={f}>
                      Form {f}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : (
              <Field id="department" label="Department (optional)" error={formState.errors.department?.message}>
                <Input id="department" {...register("department")} />
              </Field>
            )}
            <Field id="status" label="Account status">
              <Select id="status" {...register("status")}>
                <option value="active">Active</option>
                <option value="disabled">Disabled</option>
              </Select>
            </Field>
          </div>
        </Card>

        {isStudent ? (
          <Card>
            <CardHeader>
              <CardTitle>Class and subjects</CardTitle>
              <CardDescription>Leave subjects empty to use the subjects taught in the chosen class.</CardDescription>
            </CardHeader>
            <Field id="class_id" label="Class">
              <Select id="class_id" {...register("class_id")}>
                <option value="">Not in a class yet</option>
                {options.classes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.academic_year})
                  </option>
                ))}
              </Select>
            </Field>
            <SubjectPicker subjects={options.subjects} value={subjectIds} onChange={setSubjectIds} />
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Teaching</CardTitle>
              <CardDescription>Which subject this teacher teaches to which class. Class teachers are set on the class page.</CardDescription>
            </CardHeader>
            <AssignmentRows lookups={options} value={pairs} onChange={setPairs} />
          </Card>
        )}

        <Card className="gap-3">
          <label className="flex items-start gap-3">
            <Checkbox
              className="mt-0.5"
              checked={watch("send_invite") && status === "active"}
              disabled={status !== "active"}
              onCheckedChange={(c) => setValue("send_invite", c === true)}
            />
            <span className="text-sm">
              <span className="font-semibold">Send a set-password link now</span>
              <span className="block text-muted-foreground">The link works once and expires after a few days. In development it is printed to the API console instead of being emailed.</span>
            </span>
          </label>
        </Card>

        {error && <FormAlert>{error}</FormAlert>}
        <Button type="submit" disabled={formState.isSubmitting || usesSupabase}>
          {formState.isSubmitting ? <Spinner /> : <UserPlus />} Create {label}
        </Button>
      </form>
    </div>
  );
}
