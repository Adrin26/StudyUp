from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AIInteraction, Lesson, LessonSlide, Profile, Question, QuestionAttempt, Topic
from ..schemas import ExplainIn, FeedbackIn, HintIn, LessonHelpIn, SimilarCheckIn, SimilarQuestionIn, TeacherSuggestIn
from ..permissions import require_ai_enabled, require_student, require_teacher
from ..security import get_current_user
from ..services.access import ensure_can_view_student, ensure_teaches_subject, visible_student_ids
from ..services.grading import display_answer, display_given, is_correct
from ..services.openai_service import (
    AIService,
    Hint,
    LessonHelp,
    MistakeExplanation,
    SimilarQuestion,
    StudySummary,
    TeacherSuggestions,
    answer_leaks,
    normalise_message,
    question_for_prompt,
)
from ..services.question_bank import public_question
from ..services.recommendations import recommend

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_ai_enabled)])


def _slide_text(slide: LessonSlide | None) -> str:
    if slide is None:
        return ""
    parts = [slide.title]
    for key in ("body", "formula", "example", "note"):
        if slide.content.get(key):
            parts.append(str(slide.content[key]))
    for key in ("points", "steps"):
        parts += [str(x) for x in slide.content.get(key, [])]
    return "\n".join(parts)


@router.post("/lesson-help")
def lesson_help(body: LessonHelpIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    topic = db.get(Topic, body.topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    slide = db.get(LessonSlide, body.slide_id) if body.slide_id else None
    lesson = db.scalar(select(Lesson).where(Lesson.topic_id == topic.id))
    slides = lesson.slides if lesson else []
    example_slide = next((s for s in slides if s.slide_type == "example"), None)
    try_slide = next((s for s in slides if s.slide_type == "try"), None)
    context = _slide_text(slide) or (topic.description or "")

    def fallback() -> LessonHelp:
        return LessonHelp(
            explanation=f"Let's slow down. {context.splitlines()[-1] if context else topic.description}".strip(),
            example=_slide_text(example_slide) or "Look at the worked example in this lesson and follow each step slowly.",
            hint=f"Focus on one idea at a time. Write down what you already know about {topic.name}, then compare it with the slide.",
            check_question=(try_slide.content.get("question") if try_slide else None) or f"Can you explain {topic.name} in your own words?",
        )

    prompt = (
        f"Subject topic: {topic.subject.name} — {topic.name}\n"
        f"Current lesson slide:\n{context}\n\n"
        f"Student message: \"{body.message}\"\n\n"
        "Respond to the student's message about this slide. Keep each field under 80 words."
    )
    return_value = AIService(db, user).run(
        "lesson_help",
        LessonHelp,
        "Explain concepts step by step and check understanding. If asked for an answer to an exercise, guide instead of solving it outright.",
        prompt,
        cache_payload={"topic": topic.id, "slide": body.slide_id, "msg": normalise_message(body.message)},
        fallback=fallback,
        topic_id=topic.id,
        log_prompt=body.message,
    )
    db.commit()
    return return_value


@router.post("/hint")
def hint(body: HintIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.get(Question, body.question_id)
    if q is None or q.status != "published":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")

    def fallback() -> Hint:
        skill = q.skill or "this topic"
        hints = {
            1: (f"This question tests {skill}. Underline the key information and what you are asked to find.", "What do you already know that connects to this question?"),
            2: (f"Recall the main rule or formula for {skill} and write it down before calculating.", "Which formula or fact from the lesson fits here?"),
            3: ("Work step by step and check each option (or your answer) against the question's conditions.", "Can you rule out any answers that are clearly impossible?"),
        }
        h, g = hints[body.level]
        return Hint(hint=h, guiding_question=g)

    result = AIService(db, user).run(
        "hint",
        Hint,
        "Give a hint for an exam question the student is currently attempting. NEVER state the final answer, "
        "never say which option is correct, and never compute the final value. Hint level 1 = gentle nudge, "
        "2 = name the method, 3 = outline the first step.",
        f"{question_for_prompt(q, include_answer=False)}\n\nHint level: {body.level}",
        cache_payload={"q": q.id, "level": body.level},
        fallback=fallback,
        validate=lambda h: not answer_leaks(q, f"{h.hint} {h.guiding_question}"),
        question_id=q.id,
        topic_id=q.topic_id,
        log_prompt=f"hint level {body.level}",
    )
    db.commit()
    return result


def _attempt_for(db: Session, user: Profile, attempt_id: str) -> QuestionAttempt:
    attempt = db.get(QuestionAttempt, attempt_id)
    if attempt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if user.role == "student" and attempt.student_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attempt not found")
    if user.role != "student":
        ensure_can_view_student(db, user, attempt.student_id, attempt.subject_id)
    return attempt


@router.post("/explain")
def explain(body: ExplainIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = _attempt_for(db, user, body.attempt_id)
    q = db.get(Question, attempt.question_id)
    given = display_given(q, attempt.answer)
    correct = display_answer(q)

    def fallback() -> MistakeExplanation:
        steps = [s.strip() for s in (q.explanation or "").replace("\n", ". ").split(". ") if s.strip()]
        return MistakeExplanation(
            explanation=q.explanation or f"The correct answer is {correct}.",
            why_wrong=f"You chose {given}, but the correct answer is {correct}." if not attempt.is_correct else "Your answer was correct — nice work!",
            steps=steps or [f"The correct answer is {correct}."],
            tip=f"Review the key ideas of {q.skill or 'this topic'} and try a similar question.",
            recommended_action="practice_again" if not attempt.is_correct else "move_on",
        )

    result = AIService(db, user).run(
        "explain_mistake",
        MistakeExplanation,
        "The student has already submitted an answer. Explain the correct solution clearly, identify the likely "
        "misconception behind their answer, and give 2-5 short steps. Be encouraging.",
        f"{question_for_prompt(q, include_answer=True)}\n\nStudent's answer: {given}\nCorrect: {'yes' if attempt.is_correct else 'no'}",
        cache_payload={"q": q.id, "given": normalise_message(attempt.answer)},
        fallback=fallback,
        question_id=q.id,
        topic_id=q.topic_id,
        log_prompt=f"explain attempt {attempt.id}",
    )
    db.commit()
    return result | {"your_answer": given, "correct_answer": correct, "is_correct": attempt.is_correct}


@router.post("/similar-question")
def similar_question(body: SimilarQuestionIn, user: Profile = Depends(require_student), db: Session = Depends(get_db)):
    q = db.get(Question, body.question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    attempted = db.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.student_id == user.id, QuestionAttempt.question_id == q.id))
    if not attempted:
        raise HTTPException(status.HTTP_409_CONFLICT, "Answer the question first, then ask for a similar one")

    attempted_ids = set(db.scalars(select(QuestionAttempt.question_id).where(QuestionAttempt.student_id == user.id, QuestionAttempt.topic_id == q.topic_id)))
    bank = list(db.scalars(select(Question).where(Question.topic_id == q.topic_id, Question.status == "published", Question.id != q.id)))
    bank.sort(key=lambda c: (c.id in attempted_ids, c.skill != q.skill, c.difficulty != q.difficulty, c.id))

    def fallback() -> SimilarQuestion:
        pick = bank[0] if bank else q
        opts = pick.options or []
        keys = [o["key"] for o in opts]
        return SimilarQuestion(
            question_text=f"[bank:{pick.id}]",
            options=[o["text"] for o in opts],
            correct_index=keys.index(pick.correct_answer) if pick.correct_answer in keys else 0,
            explanation=pick.explanation or "",
            difficulty=pick.difficulty,
        )

    def valid(sq: SimilarQuestion) -> bool:
        return len(sq.options) == 4 and len({o.strip().lower() for o in sq.options}) == 4 and 0 <= sq.correct_index < 4 and len(sq.question_text) > 10

    result = AIService(db, user).run(
        "similar_question",
        SimilarQuestion,
        "Write ONE new multiple-choice question that practises the same skill at the same difficulty, with "
        "different numbers or context. Provide exactly four distinct options and make sure the marked answer is correct.",
        question_for_prompt(q, include_answer=True),
        cache_payload=None,
        fallback=fallback,
        validate=valid,
        question_id=q.id,
        topic_id=q.topic_id,
        log_prompt="similar question",
    )
    data = result["data"]
    if data["question_text"].startswith("[bank:"):
        generated = db.get(Question, data["question_text"][6:-1])
        origin = "question_bank"
    else:
        # AI questions are quarantined for teacher review and never enter the bank automatically.
        generated = Question(
            subject_id=q.subject_id,
            topic_id=q.topic_id,
            question_text=data["question_text"],
            question_type="mcq",
            difficulty=data["difficulty"],
            marks=q.marks,
            options=[{"key": k, "text": t} for k, t in zip("ABCD", data["options"])],
            correct_answer="ABCD"[data["correct_index"]],
            explanation=data["explanation"],
            skill=q.skill,
            source="ai_generated",
            status="pending_review",
            created_by=user.id,
        )
        db.add(generated)
        origin = "ai_generated"
    db.commit()
    return {"interaction_id": result["interaction_id"], "origin": origin, "question": public_question(generated)}


@router.post("/similar-question/check")
def check_similar(body: SimilarCheckIn, user: Profile = Depends(require_student), db: Session = Depends(get_db)):
    q = db.get(Question, body.question_id)
    allowed = q is not None and (q.status == "published" or (q.source == "ai_generated" and q.created_by == user.id))
    if not allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    return {"is_correct": is_correct(q, body.answer), "correct_display": display_answer(q), "explanation": q.explanation}


@router.post("/recommendations")
def recommendation_summary(user: Profile = Depends(require_student), db: Session = Depends(get_db)):
    recs = recommend(db, user)
    first_name = user.full_name.split()[0]
    lines = [f"- {r['title']} ({r['reason']})" for r in recs]

    def fallback() -> StudySummary:
        if not recs:
            return StudySummary(message=f"Great start, {first_name}! Pick any subject and complete a topic quiz so I can learn what to recommend next.")
        top = recs[0]
        return StudySummary(message=f"Nice work so far, {first_name}! Your best next step: {top['title'].lower()} — {top['reason'].lower()} Short, focused practice now will make the next topic easier.")

    result = AIService(db, user).run(
        "study_summary",
        StudySummary,
        "Explain why these recommendations make sense, in 2-3 encouraging sentences addressed to the student by first name. "
        "Do not invent data beyond what is given.",
        f"Student first name: {first_name}\nRecommendations (already decided):\n" + "\n".join(lines),
        cache_payload={"user": user.id, "recs": lines},
        fallback=fallback,
        log_prompt="recommendation summary",
    )
    db.commit()
    return result | {"recommendations": recs}


@router.post("/teacher-suggestions")
def teacher_suggestions(body: TeacherSuggestIn, teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    topic = db.get(Topic, body.topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    ensure_teaches_subject(db, teacher, topic.subject_id)
    skills = sorted({s for s in db.scalars(select(Question.skill).where(Question.topic_id == topic.id)) if s})

    def fallback() -> TeacherSuggestions:
        return TeacherSuggestions(
            summary=f"{body.struggling_count} students average {body.average:.0f}% in {topic.name}.",
            likely_misconceptions=[f"Gaps in {s}" for s in skills[:3]] or ["Gaps in prerequisite knowledge"],
            suggested_activities=[
                "Run a 10-minute recap of the key method with one fully worked example.",
                "Assign a short 5-question practice set and review the most-missed question together.",
                "Pair struggling students with peers who have mastered the topic.",
            ],
        )

    result = AIService(db, user=teacher).run(
        "teacher_suggestions",
        TeacherSuggestions,
        "You assist Malaysian secondary school teachers. Suggest concise, practical classroom interventions (max 3 each).",
        f"Topic: {topic.subject.name} — {topic.name}\nSkills in this topic: {', '.join(skills)}\n"
        f"{body.struggling_count} students are struggling; their average mastery is {body.average:.0f}%.",
        cache_payload={"topic": topic.id, "avg": int(body.average // 10), "n": min(body.struggling_count, 10)},
        fallback=fallback,
        topic_id=topic.id,
        log_prompt="teacher suggestions",
    )
    db.commit()
    return result


@router.post("/feedback")
def feedback(body: FeedbackIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    interaction = db.get(AIInteraction, body.interaction_id)
    if interaction is None or interaction.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interaction not found")
    interaction.helpful = body.helpful
    db.commit()
    return {"ok": True}


@router.get("/stats")
def ai_stats(teacher: Profile = Depends(require_teacher), db: Session = Depends(get_db)):
    student_ids = list(visible_student_ids(db, teacher))
    if not student_ids:
        return {"by_kind": [], "helpful_rate": None, "most_missed": []}
    by_kind = db.execute(
        select(AIInteraction.kind, func.count(), func.sum(case((AIInteraction.helpful.is_(True), 1), else_=0)), func.count(AIInteraction.helpful))
        .where(AIInteraction.user_id.in_(student_ids))
        .group_by(AIInteraction.kind)
    ).all()
    rated = sum(r[3] for r in by_kind)
    helpful = sum(r[2] or 0 for r in by_kind)
    missed = db.execute(
        select(Question, func.count().label("wrong"))
        .join(QuestionAttempt, QuestionAttempt.question_id == Question.id)
        .where(QuestionAttempt.student_id.in_(student_ids), QuestionAttempt.is_correct.is_(False))
        .group_by(Question.id)
        .order_by(func.count().desc())
        .limit(5)
    ).all()
    return {
        "by_kind": [{"kind": k, "count": c, "rated": r} for k, c, _, r in by_kind],
        "helpful_rate": round(helpful / rated * 100, 1) if rated else None,
        "most_missed": [{"id": q.id, "question_text": q.question_text, "skill": q.skill, "wrong": w} for q, w in missed],
    }
