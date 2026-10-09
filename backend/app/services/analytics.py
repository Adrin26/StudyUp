"""Teacher analytics computed in Python from stored progress."""

from collections import defaultdict
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Profile, QuestionAttempt, StudentTopicProgress, Subject, Topic
from .mastery import mastery_level

STRUGGLING_THRESHOLD = 50
ATTENTION_OVERALL = 50
MIN_STUDENTS_FOR_ALERT = 3


def _progress_rows(db: Session, student_ids: list[str], subject_id: str | None = None) -> list[StudentTopicProgress]:
    if not student_ids:
        return []
    stmt = select(StudentTopicProgress).where(
        StudentTopicProgress.student_id.in_(student_ids), StudentTopicProgress.attempts_count > 0
    )
    if subject_id:
        stmt = stmt.where(StudentTopicProgress.subject_id == subject_id)
    return list(db.scalars(stmt))


def _avg(values: list[float]) -> float | None:
    return round(mean(values), 1) if values else None


def subject_dashboard(db: Session, subject: Subject, students: list[Profile]) -> dict:
    student_ids = [s.id for s in students]
    rows = _progress_rows(db, student_ids, subject.id)
    by_student: dict[str, dict[str, StudentTopicProgress]] = defaultdict(dict)
    for r in rows:
        by_student[r.student_id][r.topic_id] = r

    topics = list(subject.topics)
    student_rows = []
    for s in students:
        prog = by_student.get(s.id, {})
        overall = _avg([p.mastery for p in prog.values()])
        student_rows.append({
            "id": s.id,
            "name": s.full_name,
            "overall": overall,
            "level": mastery_level(overall or 0, len(prog)),
            "topics": {t.id: (prog[t.id].mastery if t.id in prog else None) for t in topics},
            "weak_topics": sum(1 for p in prog.values() if p.mastery < STRUGGLING_THRESHOLD),
        })
    student_rows.sort(key=lambda r: (r["overall"] is None, -(r["overall"] or 0)))

    topic_stats = []
    for t in topics:
        vals = [by_student[sid][t.id].mastery for sid in student_ids if t.id in by_student.get(sid, {})]
        struggling = [sid for sid in student_ids if t.id in by_student.get(sid, {}) and by_student[sid][t.id].mastery < STRUGGLING_THRESHOLD]
        topic_stats.append({
            "id": t.id,
            "name": t.name,
            "average": _avg(vals),
            "students_attempted": len(vals),
            "struggling_count": len(struggling),
            "struggling_student_ids": struggling,
            "needs_attention": bool(vals) and (mean(vals) < STRUGGLING_THRESHOLD or len(struggling) >= max(MIN_STUDENTS_FOR_ALERT, len(student_ids) // 4)),
        })

    attempts_total = (
        db.scalar(
            select(func.count()).select_from(QuestionAttempt).where(
                QuestionAttempt.subject_id == subject.id, QuestionAttempt.student_id.in_(student_ids)
            )
        )
        if student_ids
        else 0
    )
    overall_vals = [r["overall"] for r in student_rows if r["overall"] is not None]
    return {
        "subject": {"id": subject.id, "name": subject.name, "color": subject.color, "icon": subject.icon},
        "class_average": _avg(overall_vals),
        "student_count": len(students),
        "topics_needing_attention": sum(1 for t in topic_stats if t["needs_attention"]),
        "questions_attempted": attempts_total,
        "topics": topic_stats,
        "students": student_rows,
        "distribution": _distribution(overall_vals),
    }


def _distribution(values: list[float]) -> list[dict]:
    bands = [("Needs Attention", 0, 40), ("Developing", 40, 60), ("Good", 60, 80), ("Mastered", 80, 101)]
    return [{"band": name, "count": sum(1 for v in values if lo <= v < hi)} for name, lo, hi in bands]


def student_detail(db: Session, student: Profile, subject_ids: list[str] | None) -> dict:
    stmt = select(StudentTopicProgress, Topic, Subject).join(Topic, Topic.id == StudentTopicProgress.topic_id).join(
        Subject, Subject.id == StudentTopicProgress.subject_id
    ).where(StudentTopicProgress.student_id == student.id, StudentTopicProgress.attempts_count > 0)
    if subject_ids is not None:
        stmt = stmt.where(StudentTopicProgress.subject_id.in_(subject_ids))
    rows = db.execute(stmt).all()

    subjects: dict[str, dict] = {}
    for p, t, s in rows:
        entry = subjects.setdefault(s.id, {"id": s.id, "name": s.name, "color": s.color, "topics": []})
        entry["topics"].append({"id": t.id, "name": t.name, "mastery": p.mastery, "attempts": p.attempts_count, "level": mastery_level(p.mastery, p.attempts_count)})
    for entry in subjects.values():
        entry["topics"].sort(key=lambda x: x["mastery"])
        entry["average"] = _avg([x["mastery"] for x in entry["topics"]])

    att_stmt = (
        select(QuestionAttempt, Topic.name)
        .join(Topic, Topic.id == QuestionAttempt.topic_id)
        .where(QuestionAttempt.student_id == student.id)
        .order_by(QuestionAttempt.created_at.desc())
        .limit(15)
    )
    if subject_ids is not None:
        att_stmt = att_stmt.where(QuestionAttempt.subject_id.in_(subject_ids))
    recent = [
        {"id": a.id, "topic": name, "is_correct": a.is_correct, "difficulty": a.difficulty, "context": a.context, "created_at": a.created_at}
        for a, name in db.execute(att_stmt).all()
    ]
    overall = _avg([x["mastery"] for e in subjects.values() for x in e["topics"]])
    return {
        "student": {"id": student.id, "name": student.full_name, "xp": student.xp, "streak": student.current_streak},
        "overall": overall,
        "level": mastery_level(overall or 0, len(rows)),
        "subjects": sorted(subjects.values(), key=lambda e: e["name"]),
        "recent_attempts": recent,
    }


def class_overview(db: Session, students: list[Profile]) -> dict:
    student_ids = [s.id for s in students]
    rows = _progress_rows(db, student_ids)
    subject_names = {s.id: s.name for s in db.scalars(select(Subject))}
    topic_names = {t.id: (t.name, t.subject_id) for t in db.scalars(select(Topic))}

    per_student_subject: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    per_subject: dict[str, list[float]] = defaultdict(list)
    per_topic: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        per_student_subject[r.student_id][r.subject_id].append(r.mastery)
        per_topic[r.topic_id].append(r.mastery)

    for sid, subs in per_student_subject.items():
        for subj, vals in subs.items():
            per_subject[subj].append(mean(vals))

    subject_perf = sorted(
        ({"id": k, "name": subject_names.get(k, "?"), "average": round(mean(v), 1), "students": len(v)} for k, v in per_subject.items()),
        key=lambda x: x["name"],
    )

    attention = []
    for s in students:
        subs = per_student_subject.get(s.id, {})
        subject_avgs = {k: mean(v) for k, v in subs.items()}
        overall = _avg(list(subject_avgs.values()))
        concerns = sorted((k for k, v in subject_avgs.items() if v < ATTENTION_OVERALL), key=lambda k: subject_avgs[k])
        if overall is not None and (overall < ATTENTION_OVERALL or len(concerns) >= 2):
            attention.append({
                "id": s.id,
                "name": s.full_name,
                "overall": overall,
                "concerns": [{"subject": subject_names.get(k, "?"), "average": round(subject_avgs[k], 1)} for k in concerns],
            })
    attention.sort(key=lambda x: x["overall"])

    struggling = sorted(
        (
            {
                "id": tid,
                "name": topic_names[tid][0],
                "subject": subject_names.get(topic_names[tid][1], "?"),
                "average": round(mean(v), 1),
                "students_attempted": len(v),
                "struggling_count": sum(1 for m in v if m < STRUGGLING_THRESHOLD),
            }
            for tid, v in per_topic.items()
            if len(v) >= MIN_STUDENTS_FOR_ALERT and tid in topic_names
        ),
        key=lambda x: x["average"],
    )[:6]

    overall_vals = [mean([mean(v) for v in subs.values()]) for subs in per_student_subject.values()]
    return {
        "student_count": len(students),
        "class_average": _avg(overall_vals),
        "subjects": subject_perf,
        "students_needing_attention": attention,
        "struggling_topics": struggling,
        "distribution": _distribution(overall_vals),
    }


def intervention_alerts(db: Session, groups: list[tuple[str, str, list[Profile]]]) -> list[dict]:
    """groups: (class_name, subject_id, students). Flags topics where many students struggle."""
    alerts = []
    topic_lookup = {t.id: t for t in db.scalars(select(Topic))}
    subject_lookup = {s.id: s for s in db.scalars(select(Subject))}
    for class_name, subject_id, students in groups:
        ids = [s.id for s in students]
        names = {s.id: s.full_name for s in students}
        per_topic: dict[str, list[StudentTopicProgress]] = defaultdict(list)
        for r in _progress_rows(db, ids, subject_id):
            per_topic[r.topic_id].append(r)
        for tid, rows in per_topic.items():
            weak = [r for r in rows if r.mastery < STRUGGLING_THRESHOLD]
            if len(weak) >= max(MIN_STUDENTS_FOR_ALERT, len(ids) // 4):
                topic = topic_lookup[tid]
                alerts.append({
                    "class_name": class_name,
                    "subject_id": subject_id,
                    "subject": subject_lookup[subject_id].name,
                    "topic_id": tid,
                    "topic": topic.name,
                    "struggling_count": len(weak),
                    "average": round(mean(r.mastery for r in weak), 1),
                    "students": sorted(({"id": r.student_id, "name": names[r.student_id], "mastery": r.mastery} for r in weak), key=lambda x: x["mastery"]),
                })
    alerts.sort(key=lambda a: (-a["struggling_count"], a["average"]))
    return alerts
