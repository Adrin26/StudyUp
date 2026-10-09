import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Eye, EyeOff, RefreshCw, Replace, Save, Shuffle, Trash2 } from "lucide-react";
import { QuestionMeta } from "@/components/question-card";
import { Spinner } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Label, Select } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import type { QuestionFull, SubjectSummary, TeacherContext } from "@/types";

interface Filters {
  topics: { id: string; name: string; question_count: number }[];
  years: number[];
}

interface Generated {
  seed: number;
  pool_size: number;
  warnings: string[];
  difficulty_counts: Record<string, number>;
  total_marks: number;
  questions: QuestionFull[];
}

export default function ExamGeneratorPage() {
  const navigate = useNavigate();
  const { data: ctx } = useApi<TeacherContext>("/api/teachers/me");
  const { data: allSubjects } = useApi<SubjectSummary[]>("/api/subjects");
  const subjects = ctx && ctx.homeroom_classes.length ? allSubjects ?? [] : ctx?.subjects ?? [];

  const [subjectId, setSubjectId] = useState("");
  const { data: filters } = useApi<Filters>(subjectId ? `/api/practice/filters?subject_id=${subjectId}` : null);
  const [topics, setTopics] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [mix, setMix] = useState({ easy: 20, medium: 50, hard: 30 });
  const [count, setCount] = useState(20);
  const [types, setTypes] = useState<string[]>(["mcq", "short_answer"]);
  const [totalMarks, setTotalMarks] = useState(40);
  const [title, setTitle] = useState("");

  const [exam, setExam] = useState<Generated | null>(null);
  const [questions, setQuestions] = useState<QuestionFull[]>([]);
  const [showAnswers, setShowAnswers] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!subjectId && subjects.length) setSubjectId(subjects[0].id);
  }, [subjects, subjectId]);

  useEffect(() => {
    if (filters) {
      setTopics(filters.topics.filter((t) => t.question_count > 0).map((t) => t.id));
      setYears(filters.years);
      setExam(null);
      setQuestions([]);
    }
  }, [filters]);

  const subjectName = subjects.find((s) => s.id === subjectId)?.name ?? "";
  const body = () => ({
    subject_id: subjectId,
    topic_ids: topics,
    years,
    difficulty_mix: mix,
    num_questions: count,
    question_types: types,
    total_marks: totalMarks,
  });

  const generate = async () => {
    setBusy("generate");
    setError(null);
    try {
      const res = await api.post<Generated>("/api/exams/generate", body());
      setExam(res);
      setQuestions(res.questions);
      if (!title) setTitle(`${subjectName} Practice Exam`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not generate exam");
    } finally {
      setBusy(null);
    }
  };

  const replace = async (q: QuestionFull) => {
    setBusy(q.id);
    try {
      const rep = await api.post<QuestionFull>("/api/exams/replace", { ...body(), question_id: q.id, current_ids: questions.map((x) => x.id) });
      setQuestions((list) => list.map((x) => (x.id === q.id ? { ...rep, marks: q.marks } : x)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No replacement available");
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy("save");
    setError(null);
    try {
      const marks = Object.fromEntries(questions.map((q) => [q.id, q.marks]));
      const res = await api.post<{ id: string }>("/api/exams", {
        title,
        subject_id: subjectId,
        question_ids: questions.map((q) => q.id),
        marks,
        config: body(),
        seed: exam?.seed,
      });
      navigate(`/teacher/exams/${res.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save exam");
      setBusy(null);
    }
  };

  const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const mixTotal = mix.easy + mix.medium + mix.hard;
  const currentMarks = questions.reduce((s, q) => s + q.marks, 0);

  return (
    <div className="space-y-5">
      <Link to="/teacher/exams" className="inline-flex items-center gap-1 text-sm font-semibold text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Exams
      </Link>
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Exam generator</h1>
        <p className="text-muted-foreground">Questions are selected by the backend from the question bank — no AI involved.</p>
      </div>

      <Card className="gap-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label>Subject</Label>
            <Select value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Number of questions</Label>
            <Input type="number" min={1} max={100} value={count} onChange={(e) => setCount(Number(e.target.value))} />
          </div>
          <div className="space-y-1.5">
            <Label>Total marks</Label>
            <Input type="number" min={1} max={500} value={totalMarks} onChange={(e) => setTotalMarks(Number(e.target.value))} />
          </div>
        </div>

        {filters && (
          <>
            <div className="space-y-2">
              <Label>Topics</Label>
              <div className="flex flex-wrap gap-2">
                {filters.topics
                  .filter((t) => t.question_count > 0)
                  .map((t) => (
                    <label key={t.id} className="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 hover:bg-muted/50">
                      <Checkbox checked={topics.includes(t.id)} onCheckedChange={() => setTopics(toggle(topics, t.id))} />
                      <span className="text-sm font-semibold">{t.name}</span>
                      <span className="text-xs text-muted-foreground">({t.question_count})</span>
                    </label>
                  ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label>Years</Label>
              <div className="flex flex-wrap gap-2">
                {filters.years.map((y) => (
                  <label key={y} className="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 hover:bg-muted/50">
                    <Checkbox checked={years.includes(y)} onCheckedChange={() => setYears(toggle(years, y))} />
                    <span className="text-sm font-semibold">{y}</span>
                  </label>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Difficulty mix (%){mixTotal !== 100 && <span className="ml-2 text-xs text-orange-600">totals {mixTotal}% — will be normalised</span>}</Label>
            <div className="grid grid-cols-3 gap-2">
              {(["easy", "medium", "hard"] as const).map((d) => (
                <div key={d} className="space-y-1">
                  <span className="text-xs font-semibold capitalize text-muted-foreground">{d}</span>
                  <Input type="number" min={0} max={100} value={mix[d]} onChange={(e) => setMix({ ...mix, [d]: Number(e.target.value) })} />
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <Label>Question type</Label>
            <div className="flex gap-2">
              {[
                ["mcq", "Objective (MCQ)"],
                ["short_answer", "Structured"],
              ].map(([v, l]) => (
                <label key={v} className="flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 hover:bg-muted/50">
                  <Checkbox checked={types.includes(v)} onCheckedChange={() => setTypes(toggle(types, v))} />
                  <span className="text-sm font-semibold">{l}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        {error && <p className="rounded-xl bg-orange-50 px-3 py-2 text-sm text-orange-800">{error}</p>}
        <Button variant="gradient" size="lg" onClick={generate} disabled={!!busy || !topics.length || !years.length || !types.length}>
          {busy === "generate" ? <Spinner /> : exam ? <RefreshCw /> : <Shuffle />} {exam ? "Re-randomize" : "Create exam"}
        </Button>
      </Card>

      {exam && (
        <div className="space-y-4">
          <Card className="gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <CardTitle className="mr-auto text-base">Preview</CardTitle>
              <Badge variant="success">Easy {questions.filter((q) => q.difficulty === "easy").length}</Badge>
              <Badge variant="warning">Medium {questions.filter((q) => q.difficulty === "medium").length}</Badge>
              <Badge variant="danger">Hard {questions.filter((q) => q.difficulty === "hard").length}</Badge>
              <Badge variant="secondary">
                {questions.length} questions · {currentMarks} marks
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Seed {exam.seed} · selected from {exam.pool_size} matching questions
            </p>
            {exam.warnings.map((w) => (
              <p key={w} className="flex items-center gap-2 rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <AlertTriangle className="size-4" /> {w}
              </p>
            ))}
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-60 flex-1 space-y-1.5">
                <Label htmlFor="exam-title">Exam title</Label>
                <Input id="exam-title" value={title} onChange={(e) => setTitle(e.target.value)} />
              </div>
              <Button variant="outline" onClick={() => setShowAnswers(!showAnswers)}>
                {showAnswers ? <EyeOff /> : <Eye />} {showAnswers ? "Hide" : "Show"} answers
              </Button>
              <Button variant="gradient" onClick={save} disabled={!!busy || !title.trim() || questions.length === 0}>
                {busy === "save" ? <Spinner /> : <Save />} Save exam
              </Button>
            </div>
          </Card>

          <ol className="space-y-3">
            {questions.map((q, i) => (
              <Card key={q.id} className="gap-3 p-4">
                <div className="flex items-start gap-3">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-extrabold text-primary">{i + 1}</span>
                  <div className="min-w-0 flex-1 space-y-2">
                    <QuestionMeta q={q} />
                    <p className="font-semibold whitespace-pre-line">{q.question_text}</p>
                    {q.options && (
                      <div className="grid gap-1 text-sm sm:grid-cols-2">
                        {q.options.map((o) => (
                          <p key={o.key} className={showAnswers && o.key === q.correct_answer ? "font-bold text-emerald-700" : ""}>
                            {o.key}. {o.text}
                          </p>
                        ))}
                      </div>
                    )}
                    {showAnswers && (
                      <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
                        <span className="font-bold">Answer:</span> {q.correct_display}
                        {q.explanation && <span className="block text-xs text-emerald-800/80">{q.explanation}</span>}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col gap-1">
                    <Button size="icon" variant="ghost" onClick={() => replace(q)} disabled={!!busy} aria-label="Replace question" title="Replace">
                      {busy === q.id ? <Spinner /> : <Replace />}
                    </Button>
                    <Button size="icon" variant="ghost" onClick={() => setQuestions(questions.filter((x) => x.id !== q.id))} aria-label="Remove question" title="Remove">
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
