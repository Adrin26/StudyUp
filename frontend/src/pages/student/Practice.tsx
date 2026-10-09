import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronLeft, ChevronRight, History, Shuffle, Sparkles } from "lucide-react";
import { QuestionCard, QuestionMeta } from "@/components/question-card";
import { EmptyState, ErrorState, Spinner } from "@/components/states";
import { SubjectIcon } from "@/components/subject-style";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label, Select } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, qs } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { AnswerFeedback, PracticeSet, QuestionPublic, SubjectSummary } from "@/types";

interface Filters {
  subject: { id: string; name: string };
  topics: { id: string; name: string; question_count: number }[];
  years: number[];
  papers: string[];
}

export default function PracticePage() {
  const [params, setParams] = useSearchParams();
  const { data: subjects } = useApi<SubjectSummary[]>("/api/subjects");
  const subjectId = params.get("subject") ?? subjects?.[0]?.id ?? "";
  const { data: filters } = useApi<Filters>(subjectId ? `/api/practice/filters?subject_id=${subjectId}` : null);
  const initialTab = params.get("year") ? "past" : params.get("topic") ? "random" : "past";

  const setSubject = (id: string) => setParams({ subject: id });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Practice</h1>
        <p className="text-muted-foreground">SPM-style questions by year and topic, and randomized practice sets.</p>
      </div>

      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
        {subjects?.map((s) => (
          <button
            key={s.id}
            onClick={() => setSubject(s.id)}
            className={`flex shrink-0 items-center gap-2 rounded-2xl border px-3 py-2 text-sm font-semibold transition-all ${s.id === subjectId ? "border-primary bg-primary/5 shadow-sm" : "bg-card hover:bg-muted"}`}
          >
            <SubjectIcon icon={s.icon} color={s.color} size="sm" />
            {s.name}
          </button>
        ))}
      </div>

      {filters && (
        <Tabs defaultValue={initialTab} key={filters.subject.id}>
          <TabsList>
            <TabsTrigger value="past">
              <History /> Questions by year
            </TabsTrigger>
            <TabsTrigger value="random">
              <Shuffle /> Randomized practice
            </TabsTrigger>
          </TabsList>
          <TabsContent value="past">
            <PastYear filters={filters} initialYear={params.get("year")} initialTopic={params.get("topic")} />
          </TabsContent>
          <TabsContent value="random">
            <RandomPractice filters={filters} initialTopic={params.get("topic")} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

function PastYear({ filters, initialYear, initialTopic }: { filters: Filters; initialYear: string | null; initialTopic: string | null }) {
  const [topic, setTopic] = useState(initialTopic ?? "");
  const [year, setYear] = useState(initialYear ?? "");
  const [paper, setPaper] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, AnswerFeedback>>({});
  const path = `/api/practice/questions${qs({ subject_id: filters.subject.id, topic_id: topic, year, paper, difficulty, page, page_size: 10 })}`;
  const { data, error, loading, reload } = useApi<{ total: number; items: QuestionPublic[] }>(path);

  useEffect(() => setPage(1), [topic, year, paper, difficulty]);
  const pages = data ? Math.max(1, Math.ceil(data.total / 10)) : 1;

  return (
    <div className="space-y-4">
      <Card className="grid gap-3 p-4 sm:grid-cols-4">
        <FilterSelect label="Topic" value={topic} onChange={setTopic} options={filters.topics.map((t) => [t.id, `${t.name} (${t.question_count})`])} />
        <FilterSelect label="Year" value={year} onChange={setYear} options={filters.years.map((y) => [String(y), String(y)])} />
        <FilterSelect label="Paper" value={paper} onChange={setPaper} options={filters.papers.map((p) => [p, p])} />
        <FilterSelect label="Difficulty" value={difficulty} onChange={setDifficulty} options={[["easy", "Easy"], ["medium", "Medium"], ["hard", "Hard"]]} />
      </Card>

      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <Spinner className="mx-auto size-6" />}
      {data && data.items.length === 0 && <EmptyState emoji="🔍" title="No questions found" description="Try a different year or topic." />}

      <div className="space-y-3">
        {data?.items.map((q) => (
          <Card key={q.id} className="gap-3 p-4">
            <button className="flex w-full items-start gap-3 text-left" onClick={() => setOpen(open === q.id ? null : q.id)} aria-expanded={open === q.id}>
              <div className="flex-1 space-y-2">
                <QuestionMeta q={q} />
                {open !== q.id && <p className="line-clamp-2 font-semibold">{q.question_text}</p>}
              </div>
              {answers[q.id] && <span className={`text-sm font-bold ${answers[q.id].is_correct ? "text-emerald-600" : "text-orange-600"}`}>{answers[q.id].is_correct ? "✓" : "✗"}</span>}
              <ChevronDown className={`size-5 text-muted-foreground transition-transform ${open === q.id ? "rotate-180" : ""}`} />
            </button>
            {open === q.id && (
              <QuestionCard
                question={{ ...q, year: null, paper: null, topic_name: undefined }}
                feedback={answers[q.id]}
                onSubmit={async (answer) => {
                  const fb = await api.post<AnswerFeedback>("/api/practice/answer", { question_id: q.id, answer });
                  setAnswers((a) => ({ ...a, [q.id]: fb }));
                }}
              />
            )}
          </Card>
        ))}
      </div>

      {data && data.total > 10 && (
        <div className="flex items-center justify-center gap-3">
          <Button variant="outline" size="icon" disabled={page === 1} onClick={() => setPage(page - 1)} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <span className="text-sm font-semibold">
            Page {page} of {pages}
          </span>
          <Button variant="outline" size="icon" disabled={page >= pages} onClick={() => setPage(page + 1)} aria-label="Next page">
            <ChevronRight />
          </Button>
        </div>
      )}
    </div>
  );
}

function FilterSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <Select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </Select>
    </div>
  );
}

function RandomPractice({ filters, initialTopic }: { filters: Filters; initialTopic: string | null }) {
  const navigate = useNavigate();
  const available = useMemo(() => filters.topics.filter((t) => t.question_count > 0), [filters]);
  const [topics, setTopics] = useState<string[]>(initialTopic ? [initialTopic] : available.map((t) => t.id));
  const [years, setYears] = useState<number[]>(filters.years);
  const [count, setCount] = useState(10);
  const [difficulty, setDifficulty] = useState("any");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

  const generate = async () => {
    setBusy(true);
    setError(null);
    try {
      const set = await api.post<PracticeSet>("/api/practice/generate", { subject_id: filters.subject.id, topic_ids: topics, years, num_questions: count, difficulty });
      navigate(`/practice/set/${set.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate a practice set");
      setBusy(false);
    }
  };

  if (available.length === 0) return <EmptyState emoji="📭" title="No questions yet" description={`Questions for ${filters.subject.name} are coming soon.`} />;

  return (
    <Card className="gap-6">
      <div className="space-y-3">
        <p className="font-bold">Topics</p>
        <div className="grid gap-2 sm:grid-cols-2">
          {available.map((t) => (
            <label key={t.id} className="flex cursor-pointer items-center gap-3 rounded-xl border p-3 hover:bg-muted/50">
              <Checkbox checked={topics.includes(t.id)} onCheckedChange={() => setTopics(toggle(topics, t.id))} />
              <span className="flex-1 text-sm font-semibold">{t.name}</span>
              <span className="text-xs text-muted-foreground">{t.question_count} Qs</span>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <p className="font-bold">Years</p>
        <div className="flex flex-wrap gap-2">
          {filters.years.map((y) => (
            <label key={y} className="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 hover:bg-muted/50">
              <Checkbox checked={years.includes(y)} onCheckedChange={() => setYears(toggle(years, y))} />
              <span className="text-sm font-semibold">{y}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Number of questions</Label>
          <Select value={count} onChange={(e) => setCount(Number(e.target.value))}>
            {[5, 10, 15, 20, 30].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Difficulty</Label>
          <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
            <option value="any">Any</option>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </Select>
        </div>
      </div>

      {error && <p className="rounded-xl bg-orange-50 px-3 py-2 text-sm text-orange-800">{error}</p>}
      <Button variant="gradient" size="lg" onClick={generate} disabled={busy || topics.length === 0 || years.length === 0}>
        {busy ? <Spinner /> : <Sparkles />} Generate practice set
      </Button>
    </Card>
  );
}
