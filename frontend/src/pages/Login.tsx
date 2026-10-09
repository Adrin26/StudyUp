import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, FlaskConical, GraduationCap, Presentation, ShieldCheck } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Field, FormAlert } from "@/components/form";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { isOwnArea, roleHome, useAuth } from "@/lib/auth";
import type { Role } from "@/types";

interface DemoAccount {
  email: string;
  full_name: string;
  role: Role;
  teacher_types: string[];
}

const schema = z.object({
  identifier: z.string().trim().min(1, "Enter your email or username."),
  password: z.string().min(1, "Enter your password."),
});
type Values = z.infer<typeof schema>;

const DEMO_STYLE: Record<Role, { icon: typeof GraduationCap; bg: string }> = {
  admin: { icon: ShieldCheck, bg: "from-slate-600 to-slate-800" },
  teacher: { icon: Presentation, bg: "from-emerald-500 to-teal-500" },
  student: { icon: GraduationCap, bg: "from-violet-500 to-indigo-500" },
};

function demoSubtitle(a: DemoAccount) {
  if (a.role === "admin") return "School administrator";
  if (a.role === "student") return "Student · Form 4";
  return a.teacher_types.length ? a.teacher_types.map((t) => t.replace("_", " ")).join(" + ") : "Teacher";
}

export default function LoginPage() {
  const { signIn, usesSupabase, notice, clearNotice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });
  const { data: demo = [] } = useQuery({
    queryKey: ["demo-accounts"],
    queryFn: () => api.get<DemoAccount[]>("/api/auth/demo-accounts"),
    enabled: !usesSupabase,
    retry: false,
  });

  const submit = async ({ identifier, password }: Values) => {
    setError(null);
    try {
      const user = await signIn(identifier, password);
      const from = (location.state as { from?: string } | null)?.from;
      navigate(from && isOwnArea(user.role, from) ? from : roleHome(user.role), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    }
  };

  const busy = formState.isSubmitting;
  return (
    <AuthLayout title="Welcome back 👋" subtitle="Sign in with the account your school gave you.">
      {notice && !error && <FormAlert tone="info">{notice}</FormAlert>}

      <form onSubmit={handleSubmit(submit)} className="space-y-4" noValidate>
        <Field id="identifier" label={usesSupabase ? "Email" : "Email or username"} error={formState.errors.identifier?.message}>
          <Input
            id="identifier"
            autoComplete="username"
            placeholder="you@school.edu.my"
            aria-invalid={!!formState.errors.identifier}
            {...register("identifier", { onChange: clearNotice })}
          />
        </Field>
        <Field id="password" label="Password" error={formState.errors.password?.message}>
          <Input id="password" type="password" autoComplete="current-password" aria-invalid={!!formState.errors.password} {...register("password")} />
        </Field>
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm font-semibold text-primary hover:underline">
            Forgot password?
          </Link>
        </div>
        {error && <FormAlert>{error}</FormAlert>}
        <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={busy}>
          {busy ? <Spinner /> : <ArrowRight />} Sign in
        </Button>
      </form>

      {demo.length > 0 && (
        <Card className="gap-3 bg-muted/40">
          <div>
            <p className="flex items-center gap-2 text-sm font-bold">
              <FlaskConical className="size-4 text-primary" /> Demo accounts
            </p>
            <p className="text-xs text-muted-foreground">Development only · fictional demo data · password demo1234</p>
          </div>
          <div className="grid gap-2">
            {demo.map((a) => {
              const style = DEMO_STYLE[a.role];
              return (
                <button
                  key={a.email}
                  type="button"
                  disabled={busy}
                  onClick={() => submit({ identifier: a.email, password: "demo1234" })}
                  className="flex items-center gap-3 rounded-xl border bg-card p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                >
                  <div className={`flex size-9 items-center justify-center rounded-lg bg-gradient-to-br text-white ${style.bg}`}>
                    <style.icon className="size-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold">{a.full_name}</p>
                    <p className="truncate text-xs capitalize text-muted-foreground">{demoSubtitle(a)}</p>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </button>
              );
            })}
          </div>
        </Card>
      )}
    </AuthLayout>
  );
}
