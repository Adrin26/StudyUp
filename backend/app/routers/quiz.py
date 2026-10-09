from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Profile, Question, QuestionAttempt, QuestionSet, QuestionSetQuestion, Topic, utcnow
from ..schemas import AnswerIn, QuizStartIn, SetIdIn
from ..permissions import require_student
from ..services import gamification, randomizer
from ..services.grading import display_answer, display_given
from ..services.mastery import mastery_level
from ..services.progress import get_progress, record_attempt, recompute_topic, topic_progress_map
from ..services.question_bank import public_question

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

QUIZ_LENGTH = 10
RESUME_WINDOW = timedelta(hours=24)


def feedback(q: Question, attempt: QuestionAttempt, xp: int = 0) -> dict:
    return {
        "question_id": q.id,
        "attempt_id": attempt.id,
        "is_correct": attempt.is_correct,
        "your_answer": attempt.answer,
        "your_answer_display": display_given(q, attempt.answer),
        "correct_answer": q.correct_answer.split("|")[0],
        "correct_display": display_answer(q),
        "explanation": q.explanation,
        "xp_gained": xp,
    }


def owned_set(db: Session, set_id: str, student: Profile, kinds: tuple[str, ...] = ("quiz",)) -> QuestionSet:
    qs = db.get(QuestionSet, set_id)
    if qs is None or qs.owner_id != student.id or qs.kind not in kinds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")
    return qs


def set_attempts(db: Session, set_id: str, student_id: str) -> dict[str, QuestionAttempt]:
    rows = db.scalars(select(QuestionAttempt).where(QuestionAttempt.set_id == set_id, QuestionAttempt.student_id == student_id))
    return {a.question_id: a for a in rows}


def quiz_payload(db: Session, qs: QuestionSet, student: Profile) -> dict:
    attempts = set_attempts(db, qs.id, student.id)
    topic = db.get(Topic, qs.topic_id)
    return {
        "id": qs.id,
        "title": qs.title,
        "status": qs.status,
        "topic": {"id": topic.id, "name": topic.name, "subject_id": topic.subject_id},
        "questions": [public_question(item.question) for item in qs.items],
        "answers": {qid: feedback(item.question, attempts[qid]) for item in qs.items if (qid := item.question_id) in attempts},
    }


@router.post("/start")
def start_quiz(body: QuizStartIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    topic = db.get(Topic, body.topic_id)
    if topic is None or topic.status != "published" or topic.subject.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")

    active = db.scalar(
        select(QuestionSet)
        .where(QuestionSet.owner_id == student.id, QuestionSet.topic_id == topic.id, QuestionSet.kind == "quiz", QuestionSet.status == "active")
        .order_by(QuestionSet.created_at.desc())
    )
    if active and active.created_at >= utcnow() - RESUME_WINDOW:
        return quiz_payload(db, active, student)

    pool = list(db.scalars(select(Question).where(Question.topic_id == topic.id, Question.status == "published")))
    if not pool:
        raise HTTPException(status.HTTP_409_CONFLICT, "This topic has no questions yet")
    mastered_ids = set(
        db.scalars(
            select(QuestionAttempt.question_id).where(
                QuestionAttempt.student_id == student.id, QuestionAttempt.topic_id == topic.id, QuestionAttempt.is_correct.is_(True)
            )
        )
    )
    seed = randomizer.new_seed()
    chosen = randomizer.select_for_quiz(pool, QUIZ_LENGTH, seed, key=lambda q: q.id, mastered_ids=mastered_ids, difficulty=lambda q: q.difficulty)
    progress = get_progress(db, student.id, topic.id)
    qs = QuestionSet(
        kind="quiz",
        title=f"{topic.name} — Knowledge Check",
        owner_id=student.id,
        subject_id=topic.subject_id,
        topic_id=topic.id,
        seed=seed,
        config={"mastery_before": progress.mastery if progress else 0.0},
        status="active",
    )
    qs.items = [QuestionSetQuestion(question_id=q.id, position=i, marks=q.marks) for i, q in enumerate(chosen)]
    db.add(qs)
    db.commit()
    return quiz_payload(db, qs, student)


@router.get("/{set_id}")
def get_quiz(set_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    return quiz_payload(db, owned_set(db, set_id, student), student)


@router.post("/{set_id}/answer")
def answer_question(set_id: str, body: AnswerIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    qs = owned_set(db, set_id, student)
    if qs.status != "active":
        raise HTTPException(status.HTTP_409_CONFLICT, "This quiz has already been submitted")
    item = next((i for i in qs.items if i.question_id == body.question_id), None)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Question is not part of this quiz")
    existing = set_attempts(db, set_id, student.id).get(body.question_id)
    if existing:
        return feedback(item.question, existing)
    attempt, xp = record_attempt(db, student, item.question, body.answer, set_id, "quiz", body.time_spent_sec)
    db.commit()
    return feedback(item.question, attempt, xp)


@router.post("/submit")
def submit_quiz(body: SetIdIn, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    qs = owned_set(db, body.set_id, student)
    if qs.status == "completed":
        return qs.result
    attempts = set_attempts(db, qs.id, student.id)
    if not attempts:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Answer at least one question before submitting")

    total = len(qs.items)
    correct = sum(1 for a in attempts.values() if a.is_correct)
    percentage = round(correct / total * 100, 1) if total else 0.0

    before = float(qs.config.get("mastery_before", 0.0))
    progress = recompute_topic(db, student.id, qs.topic_id)
    progress.quizzes_completed = (progress.quizzes_completed or 0) + 1
    after = progress.mastery

    xp = sum(gamification.xp_for_answer(a.difficulty, a.is_correct) for a in attempts.values())
    bonus = gamification.XP_QUIZ_COMPLETE + (gamification.XP_PERFECT_QUIZ if correct == total else 0)
    gamification.award_xp(db, student, bonus, "quiz_complete", qs.id)
    qs.status = "completed"
    qs.completed_at = utcnow()
    db.flush()
    new_badges = gamification.award_badges(db, student, percentage)

    skills: dict[str, list[bool]] = {}
    wrong = []
    for item in qs.items:
        q = item.question
        a = attempts.get(q.id)
        ok = bool(a and a.is_correct)
        skills.setdefault(q.skill or "General", []).append(ok)
        if not ok:
            wrong.append({
                "question": public_question(q),
                **(feedback(q, a) if a else {"attempt_id": None, "your_answer_display": "Not answered", "correct_display": display_answer(q), "explanation": q.explanation, "is_correct": False}),
            })

    topic = db.get(Topic, qs.topic_id)
    result = {
        "set_id": qs.id,
        "topic": {"id": topic.id, "name": topic.name, "subject_id": topic.subject_id},
        "score": correct,
        "total": total,
        "percentage": percentage,
        "mastery_before": before,
        "mastery_after": after,
        "mastery_change": round(after - before, 1),
        "level": mastery_level(after),
        "strong_areas": sorted(k for k, v in skills.items() if all(v)),
        "weak_areas": sorted(k for k, v in skills.items() if not all(v)),
        "wrong_questions": wrong,
        "xp_gained": xp + bonus + sum(b.xp_reward for b in new_badges),
        "new_badges": [{"code": b.code, "name": b.name, "description": b.description, "icon": b.icon} for b in new_badges],
        "streak": gamification.effective_streak(student),
        "next_topic": _next_topic(db, student, topic),
    }
    qs.result = result
    db.commit()
    return result


@router.get("/{set_id}/results")
def quiz_results(set_id: str, student: Profile = Depends(require_student), db: Session = Depends(get_db)):
    qs = owned_set(db, set_id, student)
    if qs.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Quiz not submitted yet")
    return qs.result


def _next_topic(db: Session, student: Profile, current: Topic) -> dict | None:
    subject_topics = [t for t in current.subject.topics if t.id != current.id]
    progress = topic_progress_map(db, student.id, current.subject_id)
    not_started = [t for t in subject_topics if t.id not in progress]
    weak = sorted((t for t in subject_topics if t.id in progress and progress[t.id].mastery < 60), key=lambda t: progress[t.id].mastery)
    choice = weak[0] if weak else (not_started[0] if not_started else None)
    if choice is None:
        return None
    p = progress.get(choice.id)
    return {"id": choice.id, "name": choice.name, "mastery": p.mastery if p else 0.0, "reason": "Needs practice" if p else "Up next"}
