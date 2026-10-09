import type { ReactNode } from "react";
import { Brand } from "@/components/app-shell";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="bg-hero relative hidden flex-col justify-between overflow-hidden p-10 text-white lg:flex">
        <div className="[&_p]:text-white/80">
          <Brand />
        </div>
        <div className="space-y-6">
          <h1 className="text-5xl leading-tight font-extrabold tracking-tight text-balance">Learn. Practice. Master.</h1>
          <p className="max-w-md text-lg text-white/85">Bite-sized lessons, SPM-style practice and clear progress tracking for students, teachers and schools.</p>
          <div className="flex flex-wrap gap-3">
            {["🔥 Daily streaks", "🎯 Topic mastery", "📚 Past-year practice", "🏫 School-wide memos"].map((t) => (
              <span key={t} className="rounded-full bg-white/15 px-4 py-2 text-sm font-semibold backdrop-blur">
                {t}
              </span>
            ))}
          </div>
        </div>
        <p className="text-sm text-white/70">Built for Malaysian secondary schools.</p>
        <div className="animate-float absolute -right-16 top-24 size-72 rounded-full bg-white/10 blur-2xl" />
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md space-y-6">
          <div className="lg:hidden">
            <Brand />
          </div>
          <div>
            <h2 className="text-3xl font-extrabold tracking-tight">{title}</h2>
            <p className="text-muted-foreground">{subtitle}</p>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
