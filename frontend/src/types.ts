export type Role = "student" | "teacher" | "admin";
export type Difficulty = "easy" | "medium" | "hard";
export type LevelKey = "not_started" | "needs_attention" | "developing" | "good" | "mastered";

export interface User {
  id: string;
  email: string;
  username: string | null;
  full_name: string;
  role: Role;
  status: "active" | "disabled";
  /** Derived by the backend from current class and subject assignments. */
  teacher_types: ("class_teacher" | "subject_teacher")[];
  school: string | null;
  school_logo_url: string | null;
  class_name: string | null;
  form: number | null;
  last_login_at: string | null;
}

export interface AuditEntry {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
  actor: { id: string; name: string; role: Role } | null;
}

export interface AdminOverview {
  current_academic_year: { id: string; name: string; start_date: string; end_date: string } | null;
  counts: {
    active_students: number;
    active_teachers: number;
    classes: number;
    subjects: number;
    topics: number;
    active_assignments: number;
  };
  alerts: { kind: string; message: string; link: string | null }[];
  content: { subject: string; topics: number; topics_with_lessons: number; topics_with_questions: number }[];
  recent_accounts: { id: string; name: string; role: Role; status: string; created_at: string }[];
  recent_activity: AuditEntry[];
}

export type AccountStatus = "active" | "disabled";
export interface Ref {
  id: string;
  name: string;
}
export interface PersonRef extends Ref {
  status: AccountStatus;
}

export interface TeachingAssignment {
  id: string;
  teacher: PersonRef;
  subject: Ref;
  class: Ref & { status: "active" | "archived"; academic_year: string };
}

export interface AdminUser {
  id: string;
  full_name: string;
  email: string;
  username: string | null;
  role: Role;
  status: AccountStatus;
  student_number: string | null;
  staff_number: string | null;
  form: number | null;
  department: string | null;
  class: Ref | null;
  homeroom: Ref[];
  teaching: { id: string; subject: Ref; class: Ref }[];
  created_at: string;
  last_login_at: string | null;
}

export interface AdminUserDetail extends AdminUser {
  credentials_set: boolean;
  manageable: boolean;
  subjects: Ref[];
  enrolments: { class_id: string; class_name: string; class_status: string; academic_year: string; status: "active" | "transferred" | "withdrawn"; enrolled_at: string; left_at: string | null }[];
  recent_activity: { id: string; action: string; details: Record<string, unknown>; created_at: string; actor: Ref | null }[];
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminLookups {
  subjects: (Ref & { code: string })[];
  classes: (Ref & { form: number; academic_year_id: string; academic_year: string })[];
  teachers: PersonRef[];
  academic_years: (Ref & { is_current: boolean })[];
}

export interface AdminClass {
  id: string;
  name: string;
  form: number;
  status: "active" | "archived";
  academic_year: Ref & { is_current: boolean };
  class_teacher: PersonRef | null;
  student_count: number;
  subject_count: number;
}

export interface AdminClassDetail extends AdminClass {
  students: { id: string; full_name: string; student_number: string | null; status: AccountStatus; enrolled_at: string }[];
  former_students: { id: string; full_name: string; student_number: string | null; status: "transferred" | "withdrawn"; enrolled_at: string; left_at: string | null }[];
  teaching: TeachingAssignment[];
}

export interface AcademicTerm {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
}

export interface AcademicYear extends AcademicTerm {
  is_current: boolean;
  class_count: number;
  terms: AcademicTerm[];
}

export interface SchoolProfile {
  id: string;
  name: string;
  state: string | null;
  address: string | null;
  phone: string | null;
  email: string | null;
  logo_url: string | null;
  timezone: string;
  description: string | null;
  current_academic_year: Ref | null;
  timezones: string[];
}

export interface ImportRow {
  line: number;
  role: string | null;
  full_name: string | null;
  email: string | null;
  username: string | null;
  id_number: string | null;
  class: string | null;
  status: "ready" | "error";
  errors: string[];
}

export interface ImportPreview {
  header_errors: string[];
  rows: ImportRow[];
  summary: { total: number; ready: number; errors: number };
}

export interface ImportResult {
  created: { line: number; id: string; full_name: string; email: string; username: string; invitation_delivered: boolean | null }[];
  failed: { line: number; email: string | null; errors: string[] }[];
  summary: { created: number; failed: number };
}

export interface LinkResult {
  delivered: boolean;
  message: string;
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
  available_from: string | null;
  open: boolean;
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
  /** Set when the teacher holds answers until the due date; correctness fields are then absent. */
  feedback_hidden?: boolean;
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
  assignment: {
    id: string;
    title: string;
    instructions: string | null;
    due_date: string | null;
    available_from: string | null;
    feedback_release: "immediate" | "after_due";
    open: boolean;
    past_due: boolean;
    answers_visible: boolean;
  } | null;
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
  bookmarked: boolean;
  status: "visible" | "hidden";
  moderation_reason?: string | null;
}

export interface PostComment {
  id: string;
  parent_id: string | null;
  body: string;
  created_at: string;
  author: { id: string; name: string; role: Role };
  status: "visible" | "hidden";
  moderation_reason: string | null;
}

export interface PostDetail extends Post {
  can_comment: boolean;
  can_vote: boolean;
  can_report: boolean;
  can_moderate: boolean;
  comments: PostComment[];
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
