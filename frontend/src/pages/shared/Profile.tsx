import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { KeyRound } from "lucide-react";
import { Field, FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { supabase, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { timeAgo } from "@/lib/utils";
import { confirmMessage, confirmPasswords, newPassword } from "@/lib/validation";

const schema = z
  .object({ current_password: z.string().min(1, "Enter your current password."), new_password: newPassword, confirm: z.string() })
  .refine(confirmPasswords, confirmMessage)
  .refine((v) => v.new_password !== v.current_password, { message: "Choose a password different from your current one.", path: ["new_password"] });
type Values = z.infer<typeof schema>;

const ROLE_LABEL = { admin: "Administrator", teacher: "Teacher", student: "Student" } as const;

export default function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  const rows: [string, string | null][] = [
    ["Full name", user.full_name],
    ["Email", user.email],
    ["Username", user.username],
    ["School", user.school],
    ...(user.role === "student" ? ([["Class", user.class_name], ["Form", user.form ? `Form ${user.form}` : null]] as [string, string | null][]) : []),
    ["Last sign-in", user.last_login_at ? new Date(user.last_login_at).toLocaleString() : null],
  ];

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Profile & settings</h1>
        <p className="text-muted-foreground">Your account details are managed by your school administrator.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            Account
            <Badge variant="secondary">{ROLE_LABEL[user.role]}</Badge>
            {user.teacher_types.map((t) => (
              <Badge key={t} variant="outline" className="capitalize">
                {t.replace("_", " ")}
              </Badge>
            ))}
          </CardTitle>
          {user.role === "teacher" && <CardDescription>Class and subject responsibilities come from your current class and subject assignments.</CardDescription>}
        </CardHeader>
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt className="text-xs font-semibold text-muted-foreground uppercase">{label}</dt>
              <dd className="font-medium">{value ?? "—"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {user.role === "student" && <XpHistory />}
      <XpRules />
      <ChangePassword />
    </div>
  );
}

const XP_REASON: Record<string, string> = {
  answer: "Answering questions",
  quiz_complete: "Finishing quizzes",
  lesson_complete: "Finishing lessons",
  badge: "Badges",
  opening_balance: "Earned before history was kept",
};

function XpHistory() {
  const { data } = useApi<{ total: number; by_reason: Record<string, number>; recent: { id: string; amount: number; reason: string; created_at: string }[] }>("/api/students/me/xp");
  if (!data) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your XP: {data.total}</CardTitle>
        <CardDescription>Every XP change is recorded, so your total always adds up.</CardDescription>
      </CardHeader>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {Object.entries(data.by_reason).map(([reason, amount]) => (
          <div key={reason} className="flex justify-between text-sm">
            <dt>{XP_REASON[reason] ?? reason}</dt>
            <dd className="font-bold">{amount}</dd>
          </div>
        ))}
      </dl>
      {data.recent.length > 0 && (
        <ul className="space-y-1 border-t pt-3 text-sm">
          {data.recent.slice(0, 10).map((e) => (
            <li key={e.id} className="flex justify-between">
              <span className="text-muted-foreground">
                {XP_REASON[e.reason] ?? e.reason} · {timeAgo(e.created_at)}
              </span>
              <span className="font-semibold text-emerald-700">+{e.amount}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function XpRules() {
  const { data } = useApi<{ xp_per_level: number; earning: { label: string; xp: string; note: string }[]; not_awarded: string[] }>("/api/gamification/rules");
  if (!data) return null;
  return (
    <Card>
      <CardHeader>
        <CardTitle>How XP is earned</CardTitle>
        <CardDescription>XP is awarded by the server. Every {data.xp_per_level} XP is a new level.</CardDescription>
      </CardHeader>
      <ul className="space-y-2 text-sm">
        {data.earning.map((r) => (
          <li key={r.label}>
            <span className="font-semibold">{r.label}</span>: {r.xp} XP <span className="text-muted-foreground">— {r.note}</span>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">No XP for: {data.not_awarded.join(", ").toLowerCase()}.</p>
    </Card>
  );
}

function ChangePassword() {
  const { setToken } = useAuth();
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState, reset } = useForm<Values>({ resolver: zodResolver(schema) });

  const submit = async ({ current_password, new_password }: Values) => {
    setError(null);
    setDone(false);
    try {
      if (supabase) {
        const { error: e } = await supabase.auth.updateUser({ password: new_password });
        if (e) throw new Error(e.message);
      } else {
        const res = await api.post<{ access_token: string }>("/api/auth/change-password", { current_password, new_password });
        setToken(res.access_token);
      }
      reset();
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not change the password");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Change password</CardTitle>
        <CardDescription>Other devices signed in to this account will be signed out.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit(submit)} className="grid gap-4 sm:max-w-md" noValidate>
        {!supabase && (
          <Field id="current_password" label="Current password" error={formState.errors.current_password?.message}>
            <Input id="current_password" type="password" autoComplete="current-password" {...register("current_password")} />
          </Field>
        )}
        <Field id="new_password" label="New password" error={formState.errors.new_password?.message} hint="At least 8 characters, with a letter and a number.">
          <Input id="new_password" type="password" autoComplete="new-password" {...register("new_password")} />
        </Field>
        <Field id="confirm" label="Confirm new password" error={formState.errors.confirm?.message}>
          <Input id="confirm" type="password" autoComplete="new-password" {...register("confirm")} />
        </Field>
        {error && <FormAlert>{error}</FormAlert>}
        {done && <FormAlert tone="success">Password updated.</FormAlert>}
        <Button type="submit" className="w-fit" disabled={formState.isSubmitting}>
          {formState.isSubmitting ? <Spinner /> : <KeyRound />} Update password
        </Button>
      </form>
    </Card>
  );
}
