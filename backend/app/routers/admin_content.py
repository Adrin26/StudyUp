"""Admin content management: subjects, topics, objectives, lessons and the question bank.

Students and teachers only see published records through the learning routes.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    CONTENT_STATUSES,
    LearningObjective,
    Lesson,
    Profile,
    Question,
    QuestionAttempt,
    Subject,
    SubjectFormLevel,
    Topic,
    TopicPrerequisite,
)
from ..permissions import require_admin
from ..schemas import ObjectiveIn, QuestionMetaIn, StatusIn, SubjectIn, TopicIn
from ..services import audit, storage

router = APIRouter(prefix="/api/admin", tags=["admin-content"])


def _status(value: str) -> str:
    if value not in CONTENT_STATUSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Status must be draft, published or archived")
    return value


def _subject(db: Session, subject_id: str) -> Subject:
    subject = db.get(Subject, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    return subject


def _topic(db: Session, topic_id: str) -> Topic:
    topic = db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Topic not found")
    return topic


def _subject_out(s: Subject) -> dict:
    return {
        "id": s.id, "code": s.code, "name": s.name, "icon": s.icon, "color": s.color,
        "description": s.description, "sort_order": s.sort_order, "status": s.status,
        "forms": sorted(f.form for f in s.form_levels),
        "topic_count": len(s.topics),
    }


@router.get("/subjects")
def list_subjects(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return [_subject_out(s) for s in db.scalars(select(Subject).order_by(Subject.sort_order, Subject.name))]


@router.post("/subjects", status_code=status.HTTP_201_CREATED)
def create_subject(body: SubjectIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Subject.id).where(func.lower(Subject.code) == body.code.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "That subject code is already used")
    subject = Subject(code=body.code, name=body.name, description=body.description, icon=body.icon, color=body.color, status="draft")
    db.add(subject)
    db.flush()
    for form in sorted(set(body.forms)):
        db.add(SubjectFormLevel(subject_id=subject.id, form=form))
    audit.record(db, "subject.create", "subject", subject.id, actor=admin, request=request, details={"code": subject.code})
    db.commit()
    db.refresh(subject)
    return _subject_out(subject)


@router.patch("/subjects/{subject_id}")
def update_subject(subject_id: str, body: SubjectIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    subject = _subject(db, subject_id)
    taken = db.scalar(select(Subject.id).where(func.lower(Subject.code) == body.code.lower(), Subject.id != subject.id))
    if taken:
        raise HTTPException(status.HTTP_409_CONFLICT, "That subject code is already used")
    subject.code, subject.name, subject.description = body.code, body.name, body.description
    subject.icon, subject.color = body.icon, body.color
    subject.form_levels.clear()
    for form in sorted(set(body.forms)):
        subject.form_levels.append(SubjectFormLevel(form=form))
    audit.record(db, "subject.update", "subject", subject.id, actor=admin, request=request, details={"code": subject.code})
    db.commit()
    return _subject_out(subject)


@router.post("/subjects/{subject_id}/status")
def set_subject_status(subject_id: str, body: StatusIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    subject = _subject(db, subject_id)
    subject.status = _status(body.status)
    audit.record(db, "subject.status", "subject", subject.id, actor=admin, request=request, details={"status": subject.status})
    db.commit()
    return _subject_out(subject)


def _topic_out(db: Session, t: Topic) -> dict:
    prereqs = list(db.scalars(select(TopicPrerequisite.prerequisite_id).where(TopicPrerequisite.topic_id == t.id)))
    return {
        "id": t.id, "subject_id": t.subject_id, "parent_id": t.parent_id, "name": t.name, "form": t.form,
        "description": t.description, "sort_order": t.sort_order, "status": t.status,
        "objectives": [{"id": o.id, "position": o.position, "text": o.text} for o in t.objectives],
        "prerequisite_ids": prereqs,
    }


@router.get("/subjects/{subject_id}/topics")
def list_topics(subject_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    subject = _subject(db, subject_id)
    topics = db.scalars(select(Topic).where(Topic.subject_id == subject.id).order_by(Topic.sort_order, Topic.name))
    return [_topic_out(db, t) for t in topics]


@router.post("/topics", status_code=status.HTTP_201_CREATED)
def create_topic(body: TopicIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    subject = _subject(db, body.subject_id)
    parent = _topic(db, body.parent_id) if body.parent_id else None
    if parent and parent.subject_id != subject.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A subtopic must belong to the same subject")
    topic = Topic(subject_id=subject.id, parent_id=parent.id if parent else None, name=body.name, form=body.form,
                  description=body.description, sort_order=body.sort_order, status="draft")
    db.add(topic)
    db.flush()
    audit.record(db, "topic.create", "topic", topic.id, actor=admin, request=request, details={"name": topic.name, "subject": subject.code})
    db.commit()
    return _topic_out(db, topic)


@router.patch("/topics/{topic_id}")
def update_topic(topic_id: str, body: TopicIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    topic = _topic(db, topic_id)
    if body.parent_id == topic.id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A topic cannot be its own parent")
    parent = _topic(db, body.parent_id) if body.parent_id else None
    if parent and (parent.subject_id != topic.subject_id or parent.parent_id == topic.id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Choose a parent in the same subject that is not a child of this topic")
    topic.name, topic.form, topic.description, topic.sort_order = body.name, body.form, body.description, body.sort_order
    topic.parent_id = parent.id if parent else None
    audit.record(db, "topic.update", "topic", topic.id, actor=admin, request=request, details={"name": topic.name})
    db.commit()
    return _topic_out(db, topic)


@router.post("/topics/{topic_id}/status")
def set_topic_status(topic_id: str, body: StatusIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    topic = _topic(db, topic_id)
    topic.status = _status(body.status)
    audit.record(db, "topic.status", "topic", topic.id, actor=admin, request=request, details={"status": topic.status})
    db.commit()
    return _topic_out(db, topic)


@router.put("/topics/{topic_id}/prerequisites")
def set_prerequisites(topic_id: str, body: dict, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    topic = _topic(db, topic_id)
    ids = body.get("prerequisite_ids") or []
    if topic.id in ids:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A topic cannot require itself")
    found = list(db.scalars(select(Topic).where(Topic.id.in_(ids), Topic.subject_id == topic.subject_id)))
    if len(found) != len(set(ids)):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Prerequisites must be topics in the same subject")
    db.execute(delete(TopicPrerequisite).where(TopicPrerequisite.topic_id == topic.id))
    for other in found:
        db.add(TopicPrerequisite(topic_id=topic.id, prerequisite_id=other.id))
    db.commit()
    return _topic_out(db, topic)


@router.post("/topics/{topic_id}/objectives", status_code=status.HTTP_201_CREATED)
def add_objective(topic_id: str, body: ObjectiveIn, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    topic = _topic(db, topic_id)
    position = body.position if body.position is not None else len(topic.objectives)
    objective = LearningObjective(topic_id=topic.id, position=position, text=body.text)
    db.add(objective)
    db.commit()
    db.refresh(topic)
    return _topic_out(db, topic)


@router.delete("/objectives/{objective_id}")
def delete_objective(objective_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    objective = db.get(LearningObjective, objective_id)
    if objective is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Objective not found")
    db.delete(objective)
    db.commit()
    return {"deleted": objective_id}


@router.post("/lessons/{lesson_id}/status")
def set_lesson_status(lesson_id: str, body: StatusIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    lesson.status = _status(body.status)
    audit.record(db, "lesson.status", "lesson", lesson.id, actor=admin, request=request, details={"status": lesson.status})
    db.commit()
    return {"id": lesson.id, "title": lesson.title, "status": lesson.status, "topic_id": lesson.topic_id}


@router.get("/questions")
def list_questions(
    subject_id: str | None = None,
    topic_id: str | None = None,
    status_: str | None = Query(None, alias="status"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(Question)
    if subject_id:
        stmt = stmt.where(Question.subject_id == subject_id)
    if topic_id:
        stmt = stmt.where(Question.topic_id == topic_id)
    if status_:
        stmt = stmt.where(Question.status == _status(status_))
    if q and q.strip():
        stmt = stmt.where(or_(Question.question_text.contains(q.strip()), Question.skill.contains(q.strip())))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Question.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [{
            "id": item.id, "subject_id": item.subject_id, "topic_id": item.topic_id, "status": item.status,
            "question_type": item.question_type, "difficulty": item.difficulty, "marks": item.marks,
            "year": item.year, "form": item.form, "source": item.source, "attribution": item.attribution,
            "question_text": item.question_text, "image_url": item.image_url,
        } for item in rows],
    }


@router.patch("/questions/{question_id}")
def update_question(question_id: str, body: QuestionMetaIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        data["status"] = _status(data["status"])
    for key, value in data.items():
        setattr(question, key, value)
    audit.record(db, "question.update", "question", question.id, actor=admin, request=request, details={"fields": ", ".join(sorted(data))})
    db.commit()
    return {"id": question.id, "status": question.status, "form": question.form, "attribution": question.attribution, "image_url": question.image_url}


@router.post("/questions/{question_id}/image")
async def upload_question_image(question_id: str, request: Request, file: UploadFile = File(...), admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    question.image_url = storage.save(await file.read(), file.filename or "image", file.content_type or "", images_only=True)
    audit.record(db, "question.image", "question", question.id, actor=admin, request=request)
    db.commit()
    return {"id": question.id, "image_url": question.image_url}


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    used = db.scalar(select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.question_id == question.id))
    if used:
        raise HTTPException(status.HTTP_409_CONFLICT, "This question has answers recorded. Archive it instead of deleting it.")
    db.delete(question)
    db.commit()
    return {"deleted": question_id}
