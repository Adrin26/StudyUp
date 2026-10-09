export type Role = "student" | "teacher" | "admin";
export type Difficulty = "easy" | "medium" | "hard";
export type LevelKey = "not_started" | "needs_attention" | "developing" | "good" | "mastered";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  teacher_types: ("class_teacher" | "subject_teacher")[];
  school: string | null;
  class_name: string | null;
  form: number | null;
}

export interface Level {
  key: LevelKey;
  label: string;
}

export interface SubjectSummary {
  id: string;
  code?: string;
  name: string;
  icon: string;
  color: string;
  description?: string;
  progress: number;
  topics_total: number;
  topics_mastered: number;
  topics_started: number;
  weakest_topic?: TopicSummary | null;
}

export interface TopicSummary {
  id: string;
  subject_id: string;
  name: string;
  description: string | null;
  form: number | null;
  mastery: number;
  attempts: number;
  level: Level;
  question_count?: number;
}

export interface Recommendation {
  kind: "assignment" | "practice_topic" | "resume_lesson" | "start_topic" | "past_year";
  title: string;
  reason: string;
  subject?: string;
  mastery?: number;
  action: { type: "assignment" | "topic" | "lesson" | "past_year"; set_id?: string; topic_id?: string; subject_id?: string; year?: number };
}

export interface BadgeInfo {
  code: string;
  name: string;
  description: string;
  icon: string;
  earned: boolean;
  earned_at?: string | null;
}

export interface AssignmentInfo {
  id: string;
  title: string;
  instructions: string | null;
  teacher: string;
  subject: string;
  topic: string | null;
  set_id: string;
  due_date: string | null;
  status: "assigned" | "completed";
  score: number | null;
}

export interface Stats {
  overall_progress: number;
  topics_mastered: number;
  topics_total: number;
  questions_answered: number;
  average_score: number;
  xp: number;
  streak: number;
  longest_streak: number;
  level: number;
  xp_into_level: number;
  xp_for_next: number;
  progress: number;
  weekly_goal: { target: number; done: number };
  daily_challenge: { target: number; done: number };
}

export interface Dashboard {
  stats: Stats;
  subjects: SubjectSummary[];
  recommendations: Recommendation[];
  assignments: AssignmentInfo[];
  badges: BadgeInfo[];
}

export interface Option {
  key: string;
  text: string;
}

export interface QuestionPublic {
  id: string;
  subject_id: string;
  topic_id: string;
  year: number | null;
  paper: string | null;
  question_number: number | null;
  question_text: string;
  question_type: "mcq" | "short_answer";
  difficulty: Difficulty;
  marks: number;
  options: Option[] | null;
  image_url: string | null;
  skill: string | null;
  source: string;
  topic_name?: string;
  subject_name?: string;
}

export interface QuestionFull extends QuestionPublic {
  correct_answer: string;
  correct_display: string;
  explanation: string | null;
}

export interface AnswerFeedback {
  question_id: string;
  attempt_id: string;
  is_correct: boolean;
  your_answer: string;
  your_answer_display: string;
  correct_answer: string;
  correct_display: string;
  explanation: string | null;
  xp_gained: number;
  topic_mastery?: number;
}

export interface QuizSession {
  id: string;
  title: string;
  status: "active" | "completed";
  topic: { id: string; name: string; subject_id: string };
  questions: QuestionPublic[];
  answers: Record<string, AnswerFeedback>;
}

export interface QuizResult {
  set_id: string;
  topic: { id: string; name: string; subject_id: string };
  score: number;
  total: number;
  percentage: number;
  mastery_before: number;
  mastery_after: number;
  mastery_change: number;
  level: Level;
  strong_areas: string[];
  weak_areas: string[];
  wrong_questions: (Partial<AnswerFeedback> & { question: QuestionPublic; your_answer_display: string; correct_display: string })[];
  xp_gained: number;
  new_badges: { code: string; name: string; description: string; icon: string }[];
  streak: number;
  next_topic: { id: string; name: string; mastery: number; reason: string } | null;
}

export interface Slide {
  id: string;
  position: number;
  type: "intro" | "concept" | "formula" | "example" | "tip" | "try";
  title: string;
  content: {
    emoji?: string;
    body?: string;
    points?: string[];
    highlight?: string;
    formula?: string;
    note?: string;
    example?: string;
    steps?: string[];
    answer?: string | number;
    question?: string;
    options?: string[];
    explanation?: string;
  };
}

export interface LessonData {
  id: string;
  topic_id: string;
  title: string;
  summary: string;
  estimated_minutes: number;
  current_slide: number;
  completed: boolean;
  slides: Slide[];
}

export interface AIResponse<T> {
  interaction_id: string;
  cached: boolean;
  source: "openai" | "fallback" | "cache";
  data: T;
}

export interface PracticeSet {
  id: string;
  kind: "practice" | "assignment";
  title: string;
  seed: number | null;
  status: string;
  assignment: { id: string; title: string; instructions: string | null; due_date: string | null } | null;
  questions: QuestionPublic[];
  answers: Record<string, AnswerFeedback>;
}

export interface Post {
  id: string;
  space: "student" | "teacher";
  title: string;
  body: string;
  category: string | null;
  subject_id: string | null;
  subject: string | null;
  topic_id: string | null;
  topic: string | null;
  score: number;
  comment_count: number;
  created_at: string;
  author: { id: string; name: string; role: Role };
  my_vote: number;
}

export interface PostDetail extends Post {
  can_comment: boolean;
  comments: { id: string; body: string; created_at: string; author: { id: string; name: string; role: Role } }[];
}

export interface TeacherContext {
  teacher_types: string[];
  homeroom_classes: { id: string; name: string; form: number; student_count: number }[];
  subjects: { id: string; name: string; color: string; icon: string; classes: { id: string; name: string }[] }[];
}

export interface SubjectDashboard {
  subject: { id: string; name: string; color: string; icon: string };
  class_average: number | null;
  student_count: number;
  topics_needing_attention: number;
  questions_attempted: number;
  topics: { id: string; name: string; average: number | null; students_attempted: number; struggling_count: number; struggling_student_ids: string[]; needs_attention: boolean }[];
  students: { id: string; name: string; overall: number | null; level: Level; topics: Record<string, number | null>; weak_topics: number }[];
  distribution: { band: string; count: number }[];
}

export interface ClassOverview {
  class: { id: string; name: string; form: number };
  student_count: number;
  class_average: number | null;
  subjects: { id: string; name: string; average: number; students: number }[];
  students_needing_attention: { id: string; name: string; overall: number; concerns: { subject: string; average: number }[] }[];
  struggling_topics: { id: string; name: string; subject: string; average: number; students_attempted: number; struggling_count: number }[];
  distribution: { band: string; count: number }[];
}

export interface Alert {
  class_name: string;
  subject_id: string;
  subject: string;
  topic_id: string;
  topic: string;
  struggling_count: number;
  average: number;
  students: { id: string; name: string; mastery: number }[];
}

export interface StudentDetail {
  student: { id: string; name: string; xp: number; streak: number };
  overall: number | null;
  level: Level;
  subjects: { id: string; name: string; color: string; average: number | null; topics: { id: string; name: string; mastery: number; attempts: number; level: Level }[] }[];
  recent_attempts: { id: string; topic: string; is_correct: boolean; difficulty: Difficulty; context: string; created_at: string }[];
}
