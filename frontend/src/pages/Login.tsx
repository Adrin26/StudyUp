import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, GraduationCap, Presentation, Sparkles } from "lucide-react";
import { Brand } from "@/components/app-shell";
import { Spinner } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface DemoAccount {
  email: string;
  full_name: string;
  role: string;
  teacher_types: string[];
}

export default function LoginPage() {
  const { signIn, usesSupabase } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoAccount[]>([]);

  useEffect(() => {
    if (!usesSupabase) api.get<DemoAccount[]>("/api/auth/demo-accounts").then(setDemo).catch(() => setDemo([]));
  }, [usesSupabase]);

  const submit = async (e?: FormEvent, override?: { email: string; password: string }) => {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await signIn(override?.email ?? email, override?.password ?? password);
      navigate(user.role === "student" ? "/" : "/teacher");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="bg-hero relative hidden flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <div className="[&_p]:text-white/80">
          <Brand />
        </div>
        <div className="space-y-6">
          <h1 className="text-5xl leading-tight font-extrabold tracking-tight text-balance">Know exactly what to learn next.</h1>
          <p className="max-w-md text-lg text-white/85">Bite-sized lessons, SPM-style practice and an AI coach that explains — not just answers.</p>
          <div className="flex flex-wrap gap-3">
            {["🔥 Daily streaks", "🎯 Topic mastery", "✨ AI hints", "📚 Past-year practice"].map((t) => (
              <span key={t} className="rounded-full bg-white/15 px-4 py-2 text-sm font-semibold backdrop-blur">
                {t}
              </span>
            ))}
          </div>
        </div>
        <p className="text-sm text-white/70">AI should make learning more personal, not replace the teacher.</p>
        <div className="animate-float absolute -right-16 top-24 size-72 rounded-full bg-white/10 blur-2xl" />
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md space-y-6">
          <div className="lg:hidden">
            <Brand />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight">Welcome back 👋</h2>
            <p className="text-muted-foreground">Sign in to continue your learning journey.</p>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@school.edu.my" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <p className="rounded-xl bg-orange-50 px-3 py-2 text-sm font-medium text-orange-800" role="alert">{error}</p>}
            <Button type="submit" variant="gradient" size="lg" className="w-full" disabled={busy}>
              {busy ? <Spinner /> : <ArrowRight />} Sign in
            </Button>
          </form>

          {demo.length > 0 && (
            <Card className="gap-3 bg-muted/40">
              <div className="flex items-center gap-2 text-sm font-bold">
                <Sparkles className="size-4 text-primary" /> Try a demo account
              </div>
              <div className="grid gap-2">
                {demo.map((a) => (
                  <button
                    key={a.email}
                    type="button"
                    disabled={busy}
                    onClick={() => submit(undefined, { email: a.email, password: "demo1234" })}
                    className="flex items-center gap-3 rounded-xl border bg-card p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
                  >
                    <div className={`flex size-9 items-center justify-center rounded-lg text-white ${a.role === "student" ? "bg-gradient-to-br from-violet-500 to-indigo-500" : "bg-gradient-to-br from-emerald-500 to-teal-500"}`}>
                      {a.role === "student" ? <GraduationCap className="size-5" /> : <Presentation className="size-5" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-bold">{a.full_name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {a.role === "student" ? "Student · Form 4" : a.teacher_types.map((t) => t.replace("_", " ")).join(" + ")}
                      </p>
                    </div>
                    <ArrowRight className="size-4 text-muted-foreground" />
                  </button>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
