import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { KeyRound, Plus, Save, Trash2, UserCheck, UserX } from "lucide-react";
import { Field, FormAlert } from "@/components/form";
import { EmptyState, ErrorState, PageLoader, Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminLookups, AdminUserDetail, LinkResult } from "@/types";
import { actionLabel, formatWhen } from "./audit";
import { ConfirmButton, PageHeader, RoleBadge, StatusBadge, errorText, formatDate, refreshAdmin, useLookups } from "./common";
import { SubjectPicker, identityFields } from "./user-fields";

type Notice = { tone: "success" | "error" | "info"; text: string } | null;

export default function UserDetailPage() {
  const { userId = "" } = useParams();
  const location = useLocation();
  const initial = location.state as { notice?: string; delivered?: boolean } | null;
  const [notice, setNotice] = useState<Notice>(initial?.notice ? { tone: initial.delivered === false ? "info" : "success", text: initial.notice } : null);
  const { usesSupabase } = useAuth();
  const lookups = useLookups();
  const { data: user, error, isPending, refetch } = useQuery({
    queryKey: ["admin", "user", userId],
    queryFn: () => api.get<AdminUserDetail>(`/api/admin/users/${userId}`),
  });

  if (isPending || lookups.isPending) return <PageLoader rows={0} />;
  if (error || !user) return <ErrorState message={error?.message ?? "Could not load this user"} onRetry={() => refetch()} />;

  const act = async (path: string, done: string) => {
    await api.post(`/api/admin/users/${user.id}/${path}`);
    await refreshAdmin();
    setNotice({ tone: "success", text: done });
  };

  const sendLink = async () => {
    const res = await api.post<LinkResult>(`/api/admin/users/${user.id}/reset-password`);
    setNotice({ tone: res.delivered ? "success" : "info", text: res.message });
    await refreshAdmin();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={user.full_name}
        back={{ to: "/admin/users", label: "Users" }}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <RoleBadge role={user.role} />
            <StatusBadge status={user.status} />
            {user.homeroom.length > 0 && <Badge variant="outline">Class teacher</Badge>}
            {user.teaching.length > 0 && <Badge variant="outline">Subject teacher</Badge>}
          </span>
        }
        actions={
          user.manageable && (
            <>
              {user.status === "active" && !usesSupabase && (
                <ConfirmButton
                  trigger={(open) => (
                    <Button variant="outline" onClick={open}>
                      <KeyRound /> {user.credentials_set ? "Send password reset link" : "Send set-password link"}
                    </Button>
                  )}
                  title={user.credentials_set ? "Send a password reset link?" : "Send a set-password link?"}
                  description={
                    <>
                      {user.full_name} will receive a single-use link at <strong>{user.email}</strong> to choose a new password. Any earlier link stops working. You will not see the password.
                    </>
                  }
                  confirmLabel="Send link"
                  onConfirm={sendLink}
                />
              )}
              {user.status === "active" ? (
                <ConfirmButton
                  trigger={(open) => (
                    <Button variant="outline" onClick={open}>
                      <UserX /> Disable
                    </Button>
                  )}
                  title={`Disable ${user.full_name}?`}
                  description="They are signed out everywhere and cannot sign in until reactivated. Their records are kept."
                  confirmLabel="Disable account"
                  destructive
                  onConfirm={() => act("disable", "Account disabled. Existing sessions no longer work.")}
                />
              ) : (
                <Button variant="outline" onClick={() => act("reactivate", "Account reactivated.").catch((e) => setNotice({ tone: "error", text: errorText(e) }))}>
                  <UserCheck /> Reactivate
                </Button>
              )}
            </>
          )
        }
      />

      {notice && <FormAlert tone={notice.tone}>{notice.text}</FormAlert>}
      {!user.manageable && <FormAlert tone="info">Admin accounts are managed with the server command (python -m app.cli). They cannot be edited here.</FormAlert>}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <ProfileCard user={user} onSaved={(text) => setNotice({ tone: "success", text })} />
          {user.role === "student" && lookups.data && (
            <>
              <ClassCard user={user} lookups={lookups.data} onSaved={(text) => setNotice({ tone: "success", text })} />
              <SubjectsCard user={user} lookups={lookups.data} onSaved={(text) => setNotice({ tone: "success", text })} />
            </>
          )}
          {user.role === "teacher" && lookups.data && <TeachingCard user={user} lookups={lookups.data} />}
        </div>

        <div className="space-y-4">
          <Card className="gap-3">
            <CardTitle className="text-base">Account</CardTitle>
            <dl className="space-y-2 text-sm">
              <Row label="Created" value={formatDate(user.created_at)} />
              <Row label="Last sign-in" value={user.last_login_at ? formatWhen(user.last_login_at) : "Never"} />
              {!usesSupabase && <Row label="Password" value={user.credentials_set ? "Set by the user" : "Waiting for the user to set one"} />}
            </dl>
          </Card>
          <Card className="gap-3">
            <CardTitle className="text-base">Recent activity</CardTitle>
            {user.recent_activity.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
            ) : (
              <ul className="space-y-2.5 text-sm">
                {user.recent_activity.map((e) => (
                  <li key={e.id}>
                    <p className="font-semibold">{actionLabel(e.action)}</p>
                    <p className="text-xs text-muted-foreground">
                      {e.actor ? e.actor.name : "System"} · {formatWhen(e.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  );
}

const profileSchema = z.object(identityFields);
type ProfileValues = z.infer<typeof profileSchema>;

function ProfileCard({ user, onSaved }: { user: AdminUserDetail; onSaved: (text: string) => void }) {
  const isStudent = user.role === "student";
  const [error, setError] = useState<string | null>(null);
  const defaults: ProfileValues = {
    full_name: user.full_name,
    email: user.email,
    username: user.username ?? "",
    id_number: (isStudent ? user.student_number : user.staff_number) ?? "",
    form: user.form ? String(user.form) : "",
    department: user.department ?? "",
  };
  const { register, handleSubmit, formState, reset } = useForm<ProfileValues>({ resolver: zodResolver(profileSchema), defaultValues: defaults });
  useEffect(() => reset(defaults), [user]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (v: ProfileValues) => {
    setError(null);
    try {
      await api.patch(`/api/admin/users/${user.id}`, {
        full_name: v.full_name,
        email: v.email,
        username: v.username || null,
        ...(isStudent ? { student_number: v.id_number, form: v.form ? Number(v.form) : null } : { staff_number: v.id_number, department: v.department || null }),
      });
      await refreshAdmin();
      onSaved("Profile saved.");
    } catch (e) {
      setError(errorText(e, "Could not save"));
    }
  };

  if (!user.manageable) {
    return (
      <Card>
        <CardTitle>Profile</CardTitle>
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          <Row label="Email" value={user.email} />
          <Row label="Username" value={user.username ?? "—"} />
        </dl>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
      </CardHeader>
      <form onSubmit={handleSubmit(save)} noValidate className="grid gap-4 sm:grid-cols-2">
        <Field id="p-name" label="Full name" error={formState.errors.full_name?.message}>
          <Input id="p-name" {...register("full_name")} />
        </Field>
        <Field id="p-id" label={isStudent ? "Student ID" : "Staff ID"} error={formState.errors.id_number?.message}>
          <Input id="p-id" {...register("id_number")} />
        </Field>
        <Field id="p-email" label="Email" error={formState.errors.email?.message}>
          <Input id="p-email" type="email" {...register("email")} />
        </Field>
        <Field id="p-username" label="Username" error={formState.errors.username?.message}>
          <Input id="p-username" {...register("username")} />
        </Field>
        {isStudent ? (
          <Field id="p-form" label="Form">
            <Select id="p-form" {...register("form")}>
              <option value="">—</option>
              {[1, 2, 3, 4, 5].map((f) => (
                <option key={f} value={f}>
                  Form {f}
                </option>
              ))}
            </Select>
          </Field>
        ) : (
          <Field id="p-dept" label="Department" error={formState.errors.department?.message}>
            <Input id="p-dept" {...register("department")} />
          </Field>
        )}
        <div className="flex flex-col justify-end gap-2 sm:col-span-2">
          {error && <FormAlert>{error}</FormAlert>}
          <Button type="submit" className="w-fit" disabled={formState.isSubmitting || !formState.isDirty}>
            {formState.isSubmitting ? <Spinner /> : <Save />} Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ClassCard({ user, lookups, onSaved }: { user: AdminUserDetail; lookups: AdminLookups; onSaved: (text: string) => void }) {
  const [classId, setClassId] = useState(user.class?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setClassId(user.class?.id ?? ""), [user.class?.id]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.put(`/api/admin/users/${user.id}/class`, { class_id: classId || null });
      await refreshAdmin();
      onSaved(classId ? "Class updated. The previous enrolment is kept in the history." : "Student withdrawn from their class.");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Class</CardTitle>
        <CardDescription>Moving a student within the same academic year records a transfer.</CardDescription>
      </CardHeader>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-56 flex-1 space-y-1.5">
          <Label htmlFor="c-class">Current class</Label>
          <Select id="c-class" value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">Not in a class</option>
            {lookups.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.academic_year})
              </option>
            ))}
          </Select>
        </div>
        <Button onClick={save} disabled={busy || classId === (user.class?.id ?? "")}>
          {busy ? <Spinner /> : <Save />} Save class
        </Button>
      </div>
      {error && <FormAlert>{error}</FormAlert>}
      {user.enrolments.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="pb-2 text-left text-xs font-semibold uppercase text-muted-foreground">Enrolment history</caption>
            <tbody className="divide-y">
              {user.enrolments.map((e) => (
                <tr key={`${e.class_id}-${e.enrolled_at}`}>
                  <td className="py-2 pr-3 font-medium">
                    {e.class_name} <span className="text-muted-foreground">({e.academic_year})</span>
                  </td>
                  <td className="py-2 pr-3">
                    <Badge variant={e.status === "active" ? "success" : "muted"} className="capitalize">
                      {e.status}
                    </Badge>
                  </td>
                  <td className="py-2 text-muted-foreground">
                    {formatDate(e.enrolled_at)} – {e.left_at ? formatDate(e.left_at) : "now"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function SubjectsCard({ user, lookups, onSaved }: { user: AdminUserDetail; lookups: AdminLookups; onSaved: (text: string) => void }) {
  const current = user.subjects.map((s) => s.id);
  const [ids, setIds] = useState(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setIds(user.subjects.map((s) => s.id)), [user.subjects]);
  const dirty = ids.length !== current.length || ids.some((i) => !current.includes(i));

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.put(`/api/admin/users/${user.id}/subjects`, { subject_ids: ids });
      await refreshAdmin();
      onSaved("Subjects updated.");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Subjects</CardTitle>
        <CardDescription>The subjects shown on the student's dashboard.</CardDescription>
      </CardHeader>
      <SubjectPicker subjects={lookups.subjects} value={ids} onChange={setIds} />
      {error && <FormAlert>{error}</FormAlert>}
      <Button className="w-fit" onClick={save} disabled={busy || !dirty}>
        {busy ? <Spinner /> : <Save />} Save subjects
      </Button>
    </Card>
  );
}

function TeachingCard({ user, lookups }: { user: AdminUserDetail; lookups: AdminLookups }) {
  const [subjectId, setSubjectId] = useState("");
  const [classId, setClassId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/admin/teacher-assignments", { teacher_id: user.id, subject_id: subjectId, class_id: classId });
      setSubjectId("");
      setClassId("");
      await refreshAdmin();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    await api.del(`/api/admin/teacher-assignments/${id}`);
    await refreshAdmin();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Teaching</CardTitle>
        <CardDescription>Access to student records comes only from these assignments.</CardDescription>
      </CardHeader>
      {user.homeroom.length > 0 && (
        <p className="text-sm">
          Class teacher of{" "}
          {user.homeroom.map((c, i) => (
            <span key={c.id}>
              {i > 0 && ", "}
              <Link to={`/admin/classes/${c.id}`} className="font-semibold text-primary hover:underline">
                {c.name}
              </Link>
            </span>
          ))}
        </p>
      )}
      {user.teaching.length === 0 ? (
        <EmptyState emoji="📚" title="No subjects assigned" description="Add a subject and class below." />
      ) : (
        <ul className="divide-y rounded-xl border">
          {user.teaching.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <span>
                <span className="font-semibold">{t.subject.name}</span> ·{" "}
                <Link to={`/admin/classes/${t.class.id}`} className="text-primary hover:underline">
                  {t.class.name}
                </Link>
              </span>
              <ConfirmButton
                trigger={(open) => (
                  <Button variant="ghost" size="sm" onClick={open} aria-label={`Remove ${t.subject.name} for ${t.class.name}`}>
                    <Trash2 />
                  </Button>
                )}
                title="Remove this assignment?"
                description={`${user.full_name} will no longer see ${t.subject.name} records for ${t.class.name}.`}
                confirmLabel="Remove"
                destructive
                onConfirm={() => remove(t.id)}
              />
            </li>
          ))}
        </ul>
      )}
      {user.manageable && user.status === "active" && (
        <div className="flex flex-wrap items-end gap-2">
          <Select aria-label="Subject" className="min-w-40 flex-1" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            <option value="">Subject…</option>
            {lookups.subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <Select aria-label="Class" className="min-w-40 flex-1" value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">Class…</option>
            {lookups.classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.academic_year})
              </option>
            ))}
          </Select>
          <Button onClick={add} disabled={busy || !subjectId || !classId}>
            {busy ? <Spinner /> : <Plus />} Assign
          </Button>
        </div>
      )}
      {error && <FormAlert>{error}</FormAlert>}
    </Card>
  );
}
