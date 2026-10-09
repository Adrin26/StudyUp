import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Award,
  BookOpen,
  CalendarCheck,
  ClipboardCheck,
  Compass,
  Crown,
  Flame,
  Footprints,
  Lock,
  Sparkles,
  Star,
  Target,
  Trophy,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { AIFeedback } from "@/components/ai-feedback";
import { LEVEL_STYLE, levelFor } from "@/components/mastery";
import { ProgressRing } from "@/components/progress-ring";
import { ErrorState, PageLoader, Spinner } from "@/components/states";
import { SubjectIcon } from "@/components/subject-style";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/useApi";
import { greeting } from "@/lib/utils";
import type { AIResponse, Dashboard, Recommendation } from "@/types";

const BADGE_ICONS: Record<string, LucideIcon> = { footprints: Footprints, sparkles: Sparkles, flame: Flame, crown: Crown, compass: Compass, target: Target };

export default function StudentDashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<Dashboard>("/api/students/me/dashboard");

  if (loading && !data) return <PageLoader rows={6} />;
  if (error || !data) return <ErrorState message={error ?? "Could not load dashboard"} onRetry={reload} />;
  const { stats } = data;
  const firstName = user?.full_name.split(" ")[0];

  return (
    <div className="space-y-6">
      <section className="bg-hero relative overflow-hidden rounded-3xl p-6 text-white shadow-xl shadow-violet-500/20 sm:p-8">
        <div className="absolute -top-10 -right-10 size-56 rounded-full bg-white/10 blur-2xl" aria-hidden />
        <div className="relative flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-4">
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">
                {greeting()}, {firstName}! 👋
              </h1>
              <p className="text-white/85">Ready to continue learning?</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <HeroChip icon={Flame} label={`${stats.streak} Day Streak`} highlight={stats.streak > 0} />
              <HeroChip icon={Star} label={`${stats.xp.toLocaleString()} XP`} />
              <HeroChip icon={Trophy} label={`${stats.topics_mastered} Topics Mastered`} />
            </div>
            <div className="max-w-sm space-y-1.5">
              <div className="flex justify-between text-xs font-semibold text-white/85">
                <span>Level {stats.level}</span>
                <span>
                  {stats.xp_into_level} / {stats.xp_for_next} XP
                </span>
              </div>
              <Progress value={stats.progress} className="h-2 bg-white/20" indicatorClassName="from-amber-300 to-pink-400" />
            </div>
          </div>
          <div className="flex items-center gap-5 self-center md:self-auto">
            <ProgressRing value={stats.overall_progress} size={136} stroke={13}>
              <span className="text-3xl font-extrabold">{Math.round(stats.overall_progress)}%</span>
              <span className="text-xs font-medium text-white/80">Overall</span>
            </ProgressRing>
          </div>
        </div>
        <div className="relative mt-6 grid grid-cols-3 gap-3 border-t border-white/15 pt-5 text-center">
          <MiniStat value={stats.questions_answered.toLocaleString()} label="Questions answered" />
          <MiniStat value={`${Math.round(stats.average_score)}%`} label="Average score" />
          <MiniStat value={`${stats.topics_mastered}/${stats.topics_total}`} label="Topics mastered" />
        </div>
      </section>

      {data.assignments.length > 0 && <Assignments items={data.assignments} />}

      <div className="grid gap-6 lg:grid-cols-3">
        <Recommendations items={data.recommendations} />
        <div className="space-y-4">
          <GoalCard icon={Zap} title="Daily challenge" subtitle="Answer 10 questions today" done={stats.daily_challenge.done} target={stats.daily_challenge.target} color="from-amber-400 to-orange-500" />
          <GoalCard icon={CalendarCheck} title="Weekly goal" subtitle={`${stats.weekly_goal.target} questions this week`} done={stats.weekly_goal.done} target={stats.weekly_goal.target} color="from-emerald-400 to-teal-500" />
        </div>
      </div>

      <section className="space-y-3">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-xl font-extrabold tracking-tight">Your subjects</h2>
            <p className="text-sm text-muted-foreground">Pick up where you left off.</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.subjects.map((s) => (
            <Link key={s.id} to={`/subjects/${s.id}`} className="group">
              <Card className="h-full transition-all group-hover:-translate-y-1 group-hover:shadow-lg group-hover:shadow-violet-500/10">
                <div className="flex items-center gap-3">
                  <SubjectIcon icon={s.icon} color={s.color} />
                  <div className="min-w-0">
                    <p className="truncate font-bold">{s.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.topics_mastered} / {s.topics_total} topics mastered
                    </p>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-muted-foreground">Progress</span>
                    <span>{Math.round(s.progress)}%</span>
                  </div>
                  <Progress value={s.progress} />
                </div>
                {s.weakest_topic && s.weakest_topic.mastery < 60 ? (
                  <p className={`text-xs font-medium ${LEVEL_STYLE[levelFor(s.weakest_topic.mastery)].text}`}>Focus: {s.weakest_topic.name} ({Math.round(s.weakest_topic.mastery)}%)</p>
                ) : (
                  <p className="text-xs text-muted-foreground">{s.topics_started === 0 ? "Not started yet — jump in!" : "Looking good! Keep it up."}</p>
                )}
                <span className="mt-auto inline-flex items-center gap-1 text-sm font-bold text-primary">
                  Continue learning <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
                </span>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-extrabold tracking-tight">Achievements</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {data.badges.map((b) => {
            const Icon = BADGE_ICONS[b.icon] ?? Award;
            return (
              <div key={b.code} className={`flex flex-col items-center gap-2 rounded-2xl border p-4 text-center ${b.earned ? "bg-card" : "bg-muted/40 opacity-70"}`} title={b.description}>
                <div className={`flex size-12 items-center justify-center rounded-2xl ${b.earned ? "bg-gradient-to-br from-amber-300 to-pink-400 text-white shadow-md" : "bg-muted text-muted-foreground"}`}>
                  {b.earned ? <Icon className="size-6" /> : <Lock className="size-5" />}
                </div>
                <p className="text-xs font-bold">{b.name}</p>
                <p className="text-[11px] leading-tight text-muted-foreground">{b.description}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function HeroChip({ icon: Icon, label, highlight }: { icon: LucideIcon; label: string; highlight?: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-bold backdrop-blur ${highlight ? "bg-orange-400/90" : "bg-white/15"}`}>
      <Icon className="size-4" /> {label}
    </span>
  );
}

function MiniStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <p className="text-xl font-extrabold sm:text-2xl">{value}</p>
      <p className="text-[11px] font-medium text-white/75 sm:text-xs">{label}</p>
    </div>
  );
}

function GoalCard({ icon: Icon, title, subtitle, done, target, color }: { icon: LucideIcon; title: string; subtitle: string; done: number; target: number; color: string }) {
  const complete = done >= target;
  return (
    <Card className="gap-3">
      <div className="flex items-center gap-3">
        <div className={`flex size-10 items-center justify-center rounded-xl bg-gradient-to-br text-white ${color}`}>
          <Icon className="size-5" />
        </div>
        <div className="flex-1">
          <p className="font-bold">{title}</p>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        {complete && <Badge variant="success">Done! 🎉</Badge>}
      </div>
      <div className="space-y-1">
        <Progress value={(Math.min(done, target) / target) * 100} indicatorClassName={color} />
        <p className="text-right text-xs font-semibold text-muted-foreground">
          {Math.min(done, target)} / {target}
        </p>
      </div>
    </Card>
  );
}

function Assignments({ items }: { items: Dashboard["assignments"] }) {
  return (
    <Card className="gap-3 border-violet-200 bg-gradient-to-r from-violet-50 to-indigo-50">
      <div className="flex items-center gap-2">
        <ClipboardCheck className="size-5 text-primary" />
        <p className="font-bold">From your teacher</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((a) => (
          <div key={a.id} className="flex items-center gap-3 rounded-xl border bg-card p-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-bold">{a.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {a.teacher} · {a.subject}
                {a.due_date && ` · Due ${new Date(a.due_date).toLocaleDateString("en-MY", { day: "numeric", month: "short" })}`}
              </p>
            </div>
            <Button asChild size="sm" variant="gradient">
              <Link to={`/practice/set/${a.set_id}`}>Start</Link>
            </Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

function recLink(r: Recommendation): string {
  switch (r.action.type) {
    case "assignment":
      return `/practice/set/${r.action.set_id}`;
    case "lesson":
      return `/topics/${r.action.topic_id}/learn`;
    case "past_year":
      return `/practice?subject=${r.action.subject_id}&year=${r.action.year}`;
    default:
      return `/topics/${r.action.topic_id}`;
  }
}

function Recommendations({ items }: { items: Recommendation[] }) {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<AIResponse<{ message: string }> | null>(null);
  const [busy, setBusy] = useState(false);

  const explain = async () => {
    setBusy(true);
    try {
      setSummary(await api.post<AIResponse<{ message: string }>>("/api/ai/recommendations"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="lg:col-span-2">
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="size-5 text-violet-500" /> Recommended for you
          </CardTitle>
          <CardDescription>Based on your recent performance.</CardDescription>
        </div>
        {items.length > 0 && !summary && (
          <Button size="sm" variant="secondary" onClick={explain} disabled={busy}>
            {busy ? <Spinner /> : <Sparkles />} Why these?
          </Button>
        )}
      </CardHeader>
      {summary && (
        <div className="animate-pop space-y-2 rounded-xl border border-violet-200 bg-violet-50/70 p-4">
          <p className="text-sm leading-relaxed text-violet-950">{summary.data.message}</p>
          <AIFeedback interactionId={summary.interaction_id} />
        </div>
      )}
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Complete a topic quiz and we'll suggest what to learn next.</p>
      ) : (
        <ol className="space-y-2">
          {items.map((r, i) => (
            <li key={i}>
              <button onClick={() => navigate(recLink(r))} className="group flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-all hover:border-primary/40 hover:bg-accent/40">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-extrabold text-primary">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <p className="font-bold">{r.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {r.subject && `${r.subject} · `}
                    {r.reason}
                  </p>
                </div>
                {r.mastery != null && <span className={`text-sm font-bold ${LEVEL_STYLE[levelFor(r.mastery)].text}`}>{Math.round(r.mastery)}%</span>}
                {r.kind === "resume_lesson" ? <BookOpen className="size-4 text-muted-foreground" /> : <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-1" />}
              </button>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
