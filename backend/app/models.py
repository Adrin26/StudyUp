"""SQLAlchemy models.

Mirrors `supabase/migrations/0001_schema.sql`. In Supabase, `profiles.id`
equals `auth.users.id` (the `users` entity is owned by Supabase Auth).
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
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


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="student")  # student | teacher | admin
    teacher_types: Mapped[list] = mapped_column(JSON, default=list)  # class_teacher | subject_teacher
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id"))
    form: Mapped[int | None] = mapped_column(Integer)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SchoolClass(Base):
    __tablename__ = "classes"
    id: Mapped[str] = pk()
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    name: Mapped[str] = mapped_column(String(100))
    form: Mapped[int] = mapped_column(Integer)
    year: Mapped[int] = mapped_column(Integer)
    class_teacher_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))


class ClassStudent(Base):
    __tablename__ = "class_students"
    class_id: Mapped[str] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[str] = pk()
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str] = mapped_column(String(50), default="book")
    color: Mapped[str] = mapped_column(String(30), default="violet")
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    topics: Mapped[list["Topic"]] = relationship(back_populates="subject", order_by="Topic.sort_order")


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[str] = pk()
    subject_id: Mapped[str] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    form: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped[Subject] = relationship(back_populates="topics")


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
    id: Mapped[str] = pk()
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=5)

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
    status: Mapped[str] = mapped_column(String(20), default="published", index=True)  # published | pending_review | rejected
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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AssignmentStudent(Base):
    __tablename__ = "assignment_students"
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="assigned")  # assigned | completed
    score: Mapped[float | None] = mapped_column(Float)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Post(Base):
    __tablename__ = "posts"
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


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[str] = pk()
    post_id: Mapped[str] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(Text)
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
