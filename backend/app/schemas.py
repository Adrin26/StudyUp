from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Difficulty = Literal["easy", "medium", "hard"]


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
