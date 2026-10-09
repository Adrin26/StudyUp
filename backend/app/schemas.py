import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Difficulty = Literal["easy", "medium", "hard"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,59}$")
ID_NUMBER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/-]{0,29}$")
TIMEZONES = ("Asia/Kuala_Lumpur", "Asia/Kuching", "Asia/Singapore", "Asia/Jakarta", "Asia/Bangkok", "UTC")


def _blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class _IdentityFields(BaseModel):
    """Shared validation for admin-managed account fields (form and CSV import)."""

    @field_validator("full_name", "email", "username", "student_number", "staff_number", "department", mode="before", check_fields=False)
    @classmethod
    def _strip(cls, v):
        return _blank_to_none(v)

    @field_validator("email", check_fields=False)
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("username", check_fields=False)
    @classmethod
    def _username(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.lower()
        if not USERNAME_RE.match(v):
            raise ValueError("Usernames are 3–60 characters: letters, numbers, dots, dashes or underscores")
        return v

    @field_validator("student_number", "staff_number", check_fields=False)
    @classmethod
    def _id_number(cls, v: str | None) -> str | None:
        if v is not None and not ID_NUMBER_RE.match(v):
            raise ValueError("IDs are up to 30 letters, numbers, '/' or '-'")
        return v.upper() if v else v


class TeachingPair(BaseModel):
    subject_id: str
    class_id: str


class UserCreateIn(_IdentityFields):
    # Admin accounts are never created through the API; use `python -m app.cli create-admin`.
    role: Literal["student", "teacher"]
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(max_length=255)
    username: str | None = None
    student_number: str | None = None
    staff_number: str | None = None
    form: int | None = Field(default=None, ge=1, le=5)
    department: str | None = Field(default=None, max_length=100)
    status: Literal["active", "disabled"] = "active"
    class_id: str | None = None
    subject_ids: list[str] = Field(default_factory=list, max_length=30)
    assignments: list[TeachingPair] = Field(default_factory=list, max_length=60)
    send_invite: bool = True

    @field_validator("class_id", mode="before")
    @classmethod
    def _class(cls, v):
        return _blank_to_none(v)

    @model_validator(mode="after")
    def _role_fields(self):
        if self.role == "student":
            if not self.student_number:
                raise ValueError("Student ID is required for students")
            if self.staff_number or self.department or self.assignments:
                raise ValueError("Staff ID, department and teaching assignments only apply to teachers")
        else:
            if not self.staff_number:
                raise ValueError("Staff ID is required for teachers")
            if self.student_number or self.class_id or self.subject_ids or self.form:
                raise ValueError("Student ID, class, subjects and form only apply to students")
        return self


class UserUpdateIn(_IdentityFields):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    username: str | None = None
    student_number: str | None = None
    staff_number: str | None = None
    form: int | None = Field(default=None, ge=1, le=5)
    department: str | None = Field(default=None, max_length=100)


class StudentClassIn(BaseModel):
    class_id: str | None = None


class SubjectIdsIn(BaseModel):
    subject_ids: list[str] = Field(default_factory=list, max_length=30)


class ImportIn(BaseModel):
    csv: str = Field(min_length=1, max_length=512_000)
    send_invites: bool = True


class SchoolUpdateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    state: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    timezone: Literal[TIMEZONES] = "Asia/Kuala_Lumpur"  # type: ignore[valid-type]
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "state", "address", "phone", "email", "logo_url", "description", mode="before")
    @classmethod
    def _strip(cls, v):
        return _blank_to_none(v)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is not None and not EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v.lower() if v else v

    @field_validator("logo_url")
    @classmethod
    def _logo(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith("https://"):
            raise ValueError("Logo URL must start with https://")
        return v


class _DateRange(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _order(self):
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after the start date")
        return self


class AcademicYearIn(_DateRange):
    name: str = Field(min_length=1, max_length=40)
    is_current: bool = False


class AcademicTermIn(_DateRange):
    name: str = Field(min_length=1, max_length=60)


class ClassCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    form: int = Field(ge=1, le=5)
    academic_year_id: str
    class_teacher_id: str | None = None


class ClassUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    form: int | None = Field(default=None, ge=1, le=5)
    class_teacher_id: str | None = None


class EnrolIn(BaseModel):
    student_ids: list[str] = Field(min_length=1, max_length=200)


class TransferIn(BaseModel):
    to_class_id: str


class TeacherAssignmentIn(BaseModel):
    teacher_id: str
    subject_id: str
    class_id: str


class LoginIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=255, description="Email or username")
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(max_length=256)


class LessonProgressIn(BaseModel):
    current_slide: int = Field(ge=0)
    completed: bool = False


class QuizStartIn(BaseModel):
    topic_id: str


class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(max_length=500)
    time_spent_sec: int | None = Field(default=None, ge=0, le=3600)


class SetIdIn(BaseModel):
    set_id: str


class PracticeAnswerIn(AnswerIn):
    set_id: str | None = None


class PracticeGenerateIn(BaseModel):
    subject_id: str
    topic_ids: list[str] = []
    years: list[int] = []
    difficulty: Literal["any", "easy", "medium", "hard"] = "any"
    num_questions: int = Field(default=10, ge=1, le=50)
    question_types: list[Literal["mcq", "short_answer"]] = []
    seed: int | None = None


class ExamGenerateIn(BaseModel):
    subject_id: str
    topic_ids: list[str] = []
    years: list[int] = []
    difficulty_mix: dict[Difficulty, float] = {"easy": 20, "medium": 50, "hard": 30}
    num_questions: int = Field(default=20, ge=1, le=100)
    question_types: list[Literal["mcq", "short_answer"]] = []
    total_marks: int | None = Field(default=None, ge=1, le=500)
    seed: int | None = None


class ExamReplaceIn(ExamGenerateIn):
    question_id: str
    current_ids: list[str]


class ExamSaveIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    subject_id: str
    question_ids: list[str] = Field(min_length=1)
    marks: dict[str, int] = {}
    total_marks: int | None = None
    config: dict = {}
    seed: int | None = None


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str | None = None
    subject_id: str
    topic_id: str | None = None
    student_ids: list[str] = Field(min_length=1)
    num_questions: int = Field(default=10, ge=1, le=30)
    due_date: date | None = None
    exam_id: str | None = None


class PostIn(BaseModel):
    space: Literal["student", "teacher"]
    title: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=1, max_length=10000)
    subject_id: str | None = None
    topic_id: str | None = None
    category: str | None = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class VoteIn(BaseModel):
    value: Literal[-1, 0, 1]


class LessonHelpIn(BaseModel):
    topic_id: str
    slide_id: str | None = None
    message: str = Field(min_length=1, max_length=600)


class HintIn(BaseModel):
    question_id: str
    level: int = Field(default=1, ge=1, le=3)


class ExplainIn(BaseModel):
    attempt_id: str


class SimilarQuestionIn(BaseModel):
    question_id: str


class SimilarCheckIn(BaseModel):
    question_id: str
    answer: str


class TeacherSuggestIn(BaseModel):
    topic_id: str
    average: float
    struggling_count: int


class FeedbackIn(BaseModel):
    interaction_id: str
    helpful: bool
