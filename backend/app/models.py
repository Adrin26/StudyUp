"""SQLAlchemy models.

Mirrors `supabase/migrations/0001_schema.sql`. In Supabase, `profiles.id`
equals `auth.users.id` (the `users` entity is owned by Supabase Auth).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import false as sa_false
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


UUID = Uuid(as_uuid=False)


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend (SQLite has no tz support)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


def pk() -> Mapped[str]:
    return mapped_column(UUID, primary_key=True, default=new_id)


class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = pk()
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Kuala_Lumpur", server_default="Asia/Kuala_Lumpur")
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), onupdate=utcnow)


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_academic_years_school_name"),
        CheckConstraint("end_date > start_date", name="ck_academic_years_dates"),
    )
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(40))  # e.g. "2026"
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    # At most one current year per school; enforced by services/school.py when switching.
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa_false())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    terms: Mapped[list["AcademicTerm"]] = relationship(order_by="AcademicTerm.start_date", cascade="all, delete-orphan")


class AcademicTerm(Base):
    __tablename__ = "academic_terms"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "name", name="uq_academic_terms_year_name"),
        CheckConstraint("end_date > start_date", name="ck_academic_terms_dates"),
    )
    id: Mapped[str] = pk()
    academic_year_id: Mapped[str] = mapped_column(ForeignKey("academic_years.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


ROLES = ("admin", "teacher", "student")
ACCOUNT_STATUSES = ("active", "disabled")


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'student')", name="ck_profiles_role"),
        CheckConstraint("status IN ('active', 'disabled')", name="ck_profiles_status"),
        UniqueConstraint("school_id", "student_number", name="uq_profiles_school_student_number"),
        UniqueConstraint("school_id", "staff_number", name="uq_profiles_school_staff_number"),
    )
    id: Mapped[str] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # Class teacher / subject teacher are not roles: they are derived from
    # classes.class_teacher_id and teacher_subjects (see services/access.py).
    role: Mapped[str] = mapped_column(String(20), default="student")
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", index=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    form: Mapped[int | None] = mapped_column(Integer)
    student_number: Mapped[str | None] = mapped_column(String(30))
    staff_number: Mapped[str | None] = mapped_column(String(30))
    department: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), onupdate=utcnow)

    @property
    def is_active(self) -> bool:
        return self.status == "active"


class LocalCredential(Base):
    """Password hashes for AUTH_MODE=local. Stands in for Supabase's auth.users; unused on Supabase."""

    __tablename__ = "local_credentials"
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[str] = pk()
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)  # sha256 hex; the raw token is never stored
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = pk()
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id", ondelete="SET NULL"), index=True)  # None = system/CLI
    action: Mapped[str] = mapped_column(String(60), index=True)  # e.g. user.create, auth.password_reset
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id", ondelete="SET NULL"), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # never passwords, tokens or secrets
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class SchoolClass(Base):
    __tablename__ = "classes"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "name", name="uq_classes_year_name"),
        CheckConstraint("status IN ('active', 'archived')", name="ck_classes_status"),
        CheckConstraint("form BETWEEN 1 AND 5", name="ck_classes_form"),
    )
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    academic_year_id: Mapped[str] = mapped_column(ForeignKey("academic_years.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))  # doubles as the class code, unique per academic year
    form: Mapped[int] = mapped_column(Integer)
    class_teacher_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    # Archived classes keep their roster history but no longer grant teacher access.
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")


ENROLMENT_STATUSES = ("active", "transferred", "withdrawn")


class ClassStudent(Base):
    """A student's enrolment in a class. Rows are closed (status + left_at), never deleted, when a student moves."""

    __tablename__ = "class_students"
    __table_args__ = (CheckConstraint("status IN ('active', 'transferred', 'withdrawn')", name="ck_class_students_status"),)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    enrolled_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


CONTENT_STATUSES = ("draft", "published", "archived")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_subjects_status"),)
    id: Mapped[str] = pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(50), default="book")
    color: Mapped[str] = mapped_column(String(30), default="violet")
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published")

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", order_by="Topic.sort_order")
    form_levels: Mapped[list["SubjectFormLevel"]] = relationship(cascade="all, delete-orphan")


class SubjectFormLevel(Base):
    """Forms this subject is offered to. Empty means every form."""

    __tablename__ = "subject_form_levels"
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)
    form: Mapped[int] = mapped_column(Integer, primary_key=True)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_topics_status"),)
    id: Mapped[str] = pk()
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    form: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published")

    subject: Mapped[Subject] = relationship(back_populates="topics")
    objectives: Mapped[list["LearningObjective"]] = relationship(order_by="LearningObjective.position", cascade="all, delete-orphan")


class LearningObjective(Base):
    __tablename__ = "learning_objectives"
    id: Mapped[str] = pk()
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)


class TopicPrerequisite(Base):
    __tablename__ = "topic_prerequisites"
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    prerequisite_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)


class StudentSubject(Base):
    __tablename__ = "student_subjects"
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True)


class TeacherSubject(Base):
    __tablename__ = "teacher_subjects"
    __table_args__ = (UniqueConstraint("teacher_id", "subject_id", "class_id"),)
    id: Mapped[str] = pk()
    teacher_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"))


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_lessons_status"),)
    id: Mapped[str] = pk()
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published")

    slides: Mapped[list["LessonSlide"]] = relationship(order_by="LessonSlide.position", cascade="all, delete-orphan")


class LessonSlide(Base):
    __tablename__ = "lesson_slides"
    id: Mapped[str] = pk()
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    slide_type: Mapped[str] = mapped_column(String(30))  # intro | concept | formula | example | steps | tip | try
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON, default=dict)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True)
    current_slide: Mapped[int] = mapped_column(Integer, default=0)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = pk()
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    paper: Mapped[str | None] = mapped_column(String(20))
    question_number: Mapped[int | None] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[str] = mapped_column(String(20), default="mcq")  # mcq | short_answer
    difficulty: Mapped[str] = mapped_column(String(10), default="medium", index=True)  # easy | medium | hard
    marks: Mapped[int] = mapped_column(Integer, default=1)
    options: Mapped[list | None] = mapped_column(JSON)  # [{"key": "A", "text": "..."}]
    correct_answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    skill: Mapped[str | None] = mapped_column(String(120))  # sub-skill used for strong/weak areas
    source: Mapped[str] = mapped_column(String(30), default="sample")  # spm_past_year | sample | teacher | ai_generated
    form: Mapped[int | None] = mapped_column(Integer)
    attribution: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)  # draft | published | archived
    created_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class QuestionSet(Base):
    """Quiz sessions, practice sets, assignments and teacher exams."""

    __tablename__ = "question_sets"
    id: Mapped[str] = pk()
    kind: Mapped[str] = mapped_column(String(20), index=True)  # quiz | practice | assignment | exam
    title: Mapped[str] = mapped_column(String(200))
    owner_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int | None] = mapped_column(Integer)
    total_marks: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | saved
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    items: Mapped[list["QuestionSetQuestion"]] = relationship(
        order_by="QuestionSetQuestion.position", cascade="all, delete-orphan"
    )


class QuestionSetQuestion(Base):
    __tablename__ = "question_set_questions"
    set_id: Mapped[str] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"), primary_key=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    marks: Mapped[int | None] = mapped_column(Integer)

    question: Mapped[Question] = relationship()


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"
    __table_args__ = (UniqueConstraint("student_id", "set_id", "question_id", name="uq_attempts_set_question"),)
    id: Mapped[str] = pk()
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"))
    set_id: Mapped[str | None] = mapped_column(ForeignKey("question_sets.id", ondelete="SET NULL"), index=True)
    answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    difficulty: Mapped[str] = mapped_column(String(10))
    context: Mapped[str] = mapped_column(String(20), default="quiz")  # quiz | practice | assignment
    time_spent_sec: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class StudentTopicProgress(Base):
    __tablename__ = "student_topic_progress"
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    mastery: Mapped[float] = mapped_column(Float, default=0)
    recent_score: Mapped[float] = mapped_column(Float, default=0)
    historical_score: Mapped[float | None] = mapped_column(Float)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    quizzes_completed: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = pk()
    teacher_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    set_id: Mapped[str] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"))
    due_date: Mapped[date | None] = mapped_column(Date)
    available_from: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # immediate | after_due: whether students see correct answers as they go or only once the due date has passed.
    feedback_release: Mapped[str] = mapped_column(String(20), default="immediate", server_default="immediate")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AssignmentStudent(Base):
    __tablename__ = "assignment_students"
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned")  # assigned | completed
    score: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ExamPublication(Base):
    """An exam opened to one class. Students may start between opens_at and closes_at; answers appear at release_at."""

    __tablename__ = "exam_publications"
    __table_args__ = (UniqueConstraint("exam_id", "class_id", name="uq_exam_publications_exam_class"),)
    id: Mapped[str] = pk()
    exam_id: Mapped[str] = mapped_column(ForeignKey("question_sets.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    opens_at: Mapped[datetime] = mapped_column(UTCDateTime())
    closes_at: Mapped[datetime] = mapped_column(UTCDateTime())
    release_at: Mapped[datetime] = mapped_column(UTCDateTime())
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    published_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"
    __table_args__ = (UniqueConstraint("publication_id", "student_id", name="uq_exam_attempts_student"),)
    id: Mapped[str] = pk()
    publication_id: Mapped[str] = mapped_column(ForeignKey("exam_publications.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    marks_awarded: Mapped[int | None] = mapped_column(Integer)
    total_marks: Mapped[int | None] = mapped_column(Integer)


class ExamAnswer(Base):
    """Kept apart from question_attempts so exam answers never feed XP, mastery or practice feedback."""

    __tablename__ = "exam_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_exam_answers_question"),)
    id: Mapped[str] = pk()
    attempt_id: Mapped[str] = mapped_column(ForeignKey("exam_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    marks_awarded: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (CheckConstraint("status IN ('visible', 'hidden')", name="ck_posts_status"),)
    id: Mapped[str] = pk()
    author_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    space: Mapped[str] = mapped_column(String(20), index=True)  # student | teacher
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"), index=True)
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    category: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    # visible | hidden. Hidden content is kept for the record but shown only to its author and moderators.
    status: Mapped[str] = mapped_column(String(20), default="visible", server_default="visible")
    moderation_reason: Mapped[str | None] = mapped_column(String(300))
    moderated_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    moderated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (CheckConstraint("status IN ('visible', 'hidden')", name="ck_comments_status"),)
    id: Mapped[str] = pk()
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    # One level of replies: a reply's parent is always a top-level comment.
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    status: Mapped[str] = mapped_column(String(20), default="visible", server_default="visible")
    moderation_reason: Mapped[str | None] = mapped_column(String(300))
    moderated_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    moderated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PostBookmark(Base):
    __tablename__ = "post_bookmarks"
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


REPORT_REASONS = ("spam", "inappropriate", "bullying", "personal_info", "off_topic", "other")


class ContentReport(Base):
    """A user's report on a post or comment, routed to the admins of the school that owns the content."""

    __tablename__ = "content_reports"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'actioned', 'dismissed')", name="ck_content_reports_status"),
        CheckConstraint("(post_id IS NULL) <> (comment_id IS NULL)", name="ck_content_reports_target"),
    )
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[str | None] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    comment_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(30))
    details: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class PostVote(Base):
    __tablename__ = "post_votes"
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=1)


class Badge(Base):
    __tablename__ = "badges"
    id: Mapped[str] = pk()
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(300))
    icon: Mapped[str] = mapped_column(String(50))
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)


class StudentBadge(Base):
    __tablename__ = "student_badges"
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    badge_id: Mapped[str] = mapped_column(ForeignKey("badges.id", ondelete="CASCADE"), primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


MEMO_AUDIENCES = ("all", "teachers", "students")


class SchoolMemo(Base):
    __tablename__ = "school_memos"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_memos_status"),
        CheckConstraint("audience IN ('all', 'teachers', 'students')", name="ck_memos_audience"),
    )
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(String(20), default="all")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    publish_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    requires_acknowledgement: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    attachments: Mapped[list["MemoAttachment"]] = relationship(cascade="all, delete-orphan")


class MemoAttachment(Base):
    __tablename__ = "memo_attachments"
    id: Mapped[str] = pk()
    memo_id: Mapped[str] = mapped_column(ForeignKey("school_memos.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(300))


class MemoRead(Base):
    __tablename__ = "memo_reads"
    memo_id: Mapped[str] = mapped_column(ForeignKey("school_memos.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class MemoAcknowledgement(Base):
    __tablename__ = "memo_acknowledgements"
    memo_id: Mapped[str] = mapped_column(ForeignKey("school_memos.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    acknowledged_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class XPEvent(Base):
    """Ledger of every XP change, so totals can be explained and recalculated if the rules change."""

    __tablename__ = "student_xp_events"
    id: Mapped[str] = pk()
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    # answer | quiz_complete | lesson_complete | badge | opening_balance
    reason: Mapped[str] = mapped_column(String(30))
    ref_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


CALENDAR_KINDS = ("event", "holiday", "exam", "meeting", "deadline")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_calendar_events_dates"),
        CheckConstraint("audience IN ('all', 'teachers', 'students')", name="ck_calendar_events_audience"),
    )
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="event")
    audience: Mapped[str] = mapped_column(String(20), default="all")
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(ForeignKey("profiles.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AICache(Base):
    __tablename__ = "ai_cache"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    response: Mapped[dict] = mapped_column(JSON)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AIInteraction(Base):
    __tablename__ = "ai_interactions"
    id: Mapped[str] = pk()
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    prompt: Mapped[str | None] = mapped_column(Text)
    response: Mapped[dict] = mapped_column(JSON)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="openai")  # openai | fallback
    helpful: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
