"""Populate the database with a realistic demo school.

Usage:  python -m app.seed            (drops and recreates all tables)
"""

import random
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import Base, SessionLocal, engine
from ..models import (
    Assignment,
    AssignmentStudent,
    ClassStudent,
    Comment,
    Lesson,
    LessonProgress,
    LessonSlide,
    Notification,
    Post,
    PostVote,
    Profile,
    Question,
    QuestionAttempt,
    QuestionSet,
    QuestionSetQuestion,
    School,
    SchoolClass,
    StudentSubject,
    StudentTopicProgress,
    Subject,
    TeacherSubject,
    Topic,
    utcnow,
)
from ..services import gamification, passwords
from ..services.progress import recompute_topic
from .catalog import SUBJECTS, TOPICS
from .lessons import LESSONS
from .questions import build_questions

YEARS = [2019, 2020, 2021, 2022, 2023, 2024]

BESTARI = ["Aisyah Rahman", "Ali Hassan", "Sarah Lim", "John Raj", "Amir Hakim", "Mei Ling Tan", "Arjun Kumar",
           "Nurul Izzah", "Daniel Wong", "Farah Aziz", "Haziq Iskandar", "Priya Devi", "Kevin Ong", "Siti Khadijah"]
CEMERLANG = ["Adam Firdaus", "Chloe Tan", "Ravi Shankar", "Balqis Nadia", "Jason Lee", "Hana Sofea", "Irfan Danial", "Wei Jie Chua"]

ABILITY_OVERRIDES = {"Ali Hassan": 0.86, "Sarah Lim": 0.74, "John Raj": 0.45, "Aisyah Rahman": 0.7, "Haziq Iskandar": 0.42, "Kevin Ong": 0.5}
TOPIC_OFFSET = {"quadratic": -0.2, "electricity": -0.16, "bonding": -0.13, "independence": -0.1, "trigonometry": -0.08,
                "differentiation": -0.1, "functions": -0.04, "mole": -0.05, "linear": 0.06, "statistics": 0.08, "tenses": 0.06, "imbuhan": 0.08}
DIFF_ADJ = {"easy": 0.12, "medium": 0.0, "hard": -0.15}
AISYAH_SKIP = {"statistics", "indices", "progressions", "climate"}
AISYAH_TARGETS = {"quadratic": 0.42, "functions": 0.55, "electricity": 0.5, "linear": 0.88, "trigonometry": 0.68, "differentiation": 0.62,
                  "forces": 0.8, "mole": 0.74, "bonding": 0.6, "cell": 0.9, "independence": 0.7, "tenses": 0.92, "imbuhan": 0.9}


def email_for(name: str, domain: str) -> str:
    return f"{name.split()[0].lower()}@{domain}"


def _reset_schema() -> None:
    if engine.dialect.name == "sqlite":
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        return
    from alembic import command
    from alembic.config import Config

    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")


def run(reset: bool = True) -> None:
    settings = get_settings()
    if settings.auth_mode != "local" or settings.environment == "production" or "supabase" in str(engine.url):
        raise SystemExit(
            "The demo seed drops all tables and creates demo accounts; it only runs with AUTH_MODE=local "
            "outside production, against SQLite or a local Postgres. For Supabase, apply the migrations and create real users."
        )
    if reset:
        _reset_schema()
    elif engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
    rng = random.Random(2026)
    with SessionLocal() as db:
        gamification.ensure_badges(db)
        school, other_school = School(name="SMK Taman Ilmu", state="Selangor"), School(name="SMK Seri Bayu", state="Pulau Pinang")
        db.add_all([school, other_school])
        db.flush()

        subjects, topics = _curriculum(db, rng)
        admin = Profile(email="admin@school.demo", username="admin", full_name="Puan Zarina Admin", role="admin", school_id=school.id)
        db.add(admin)
        teachers = _teachers(db, school, other_school)
        classes, students = _classes_and_students(db, school, teachers)
        for p in [admin, *teachers.values(), *students]:
            p.username = p.username or p.email.split("@")[0]
            passwords.set_password(db, p, settings.demo_password)
        _teaching(db, teachers, classes, subjects)
        for s in students:
            for subj in subjects.values():
                db.add(StudentSubject(student_id=s.id, subject_id=subj.id))
        db.flush()

        _simulate_history(db, rng, students, topics)
        _community(db, rng, school, students, teachers, subjects, topics)
        _assignment(db, teachers["farid"], classes["4 Bestari"], subjects["MATH"], topics["quadratic"])
        db.commit()
        counts = {m.__tablename__: db.query(m).count() for m in (Profile, Question, QuestionAttempt, StudentTopicProgress, Post)}
    print("DEMO DATA seeded (development only):", counts)
    print(f"Every demo account uses the password {settings.demo_password!r}. Admin: admin@school.demo")


def _curriculum(db: Session, rng: random.Random) -> tuple[dict[str, Subject], dict[str, Topic]]:
    subjects = {}
    for i, (code, name, icon, color, desc) in enumerate(SUBJECTS):
        subjects[code] = Subject(code=code, name=name, icon=icon, color=color, description=desc, sort_order=i)
    db.add_all(subjects.values())
    db.flush()

    topics: dict[str, Topic] = {}
    question_numbers: dict[tuple, int] = {}
    for i, (key, code, name, form, desc) in enumerate(TOPICS):
        topic = Topic(subject_id=subjects[code].id, name=name, form=form, description=desc, sort_order=i)
        db.add(topic)
        db.flush()
        topics[key] = topic

        spec = LESSONS.get(key)
        if spec:
            lesson = Lesson(topic_id=topic.id, title=spec["title"], summary=spec["summary"], estimated_minutes=spec["minutes"])
            lesson.slides = [LessonSlide(position=p, slide_type=t, title=title, content=content) for p, (t, title, content) in enumerate(spec["slides"])]
            db.add(lesson)

        for j, q in enumerate(build_questions(key, rng)):
            year = YEARS[(j + i) % len(YEARS)]
            paper = "Paper 1" if q["type"] == "mcq" else "Paper 2"
            nkey = (code, year, paper)
            question_numbers[nkey] = question_numbers.get(nkey, 0) + 1
            options, correct = None, q["correct"]
            if q["type"] == "mcq":
                texts = q["options"][:]
                rng.shuffle(texts)
                options = [{"key": k, "text": t} for k, t in zip("ABCD", texts)]
                correct = "ABCD"[texts.index(q["correct"])]
            marks = 1 if q["type"] == "mcq" else (3 if q["difficulty"] == "hard" else 2)
            db.add(Question(
                subject_id=subjects[code].id, topic_id=topic.id, year=year, paper=paper,
                question_number=question_numbers[nkey], question_text=q["text"], question_type=q["type"],
                difficulty=q["difficulty"], marks=marks, options=options, correct_answer=correct,
                explanation=q["explanation"], skill=q["skill"], source="sample", status="published",
            ))
    db.flush()
    return subjects, topics


def _teachers(db: Session, school: School, other: School) -> dict[str, Profile]:
    t = {
        "farid": Profile(email="farid@teacher.demo", full_name="Cikgu Farid Ismail", role="teacher", school_id=school.id),
        "tan": Profile(email="tan@teacher.demo", full_name="Ms. Tan Li Wen", role="teacher", school_id=school.id),
        "rohana": Profile(email="rohana@teacher.demo", full_name="Puan Rohana Yusof", role="teacher", school_id=school.id),
        "lim": Profile(email="lim@teacher.demo", full_name="Mr. Lim Chee Keong", role="teacher", school_id=other.id),
    }
    db.add_all(t.values())
    db.flush()
    return t


def _classes_and_students(db: Session, school: School, teachers: dict[str, Profile]):
    year = utcnow().year
    classes = {
        "4 Bestari": SchoolClass(school_id=school.id, name="4 Bestari", form=4, year=year, class_teacher_id=teachers["farid"].id),
        "4 Cemerlang": SchoolClass(school_id=school.id, name="4 Cemerlang", form=4, year=year, class_teacher_id=teachers["rohana"].id),
    }
    db.add_all(classes.values())
    db.flush()
    students = []
    for cname, names in (("4 Bestari", BESTARI), ("4 Cemerlang", CEMERLANG)):
        for name in names:
            s = Profile(email=email_for(name, "student.demo"), full_name=name, role="student", school_id=school.id, form=4)
            db.add(s)
            db.flush()
            db.add(ClassStudent(class_id=classes[cname].id, student_id=s.id))
            students.append(s)
    db.flush()
    return classes, students


def _teaching(db: Session, teachers, classes, subjects) -> None:
    plan = {
        "farid": [("MATH", "4 Bestari"), ("MATH", "4 Cemerlang"), ("ADDMATH", "4 Bestari"), ("ADDMATH", "4 Cemerlang")],
        "tan": [("PHY", "4 Bestari"), ("CHEM", "4 Bestari"), ("ENG", "4 Bestari"), ("PHY", "4 Cemerlang")],
        "rohana": [("BIO", "4 Bestari"), ("BIO", "4 Cemerlang"), ("HIST", "4 Bestari"), ("HIST", "4 Cemerlang")],
    }
    for key, rows in plan.items():
        for code, cname in rows:
            db.add(TeacherSubject(teacher_id=teachers[key].id, subject_id=subjects[code].id, class_id=classes[cname].id))
    db.flush()


def _simulate_history(db: Session, rng: random.Random, students: list[Profile], topics: dict[str, Topic]) -> None:
    now = utcnow()
    today = gamification.today_my()
    pools = {k: list(db.scalars(select(Question).where(Question.topic_id == t.id))) for k, t in topics.items()}
    lessons = {k: db.scalar(select(Lesson).where(Lesson.topic_id == t.id)) for k, t in topics.items()}

    for s in students:
        is_demo = s.email == "aisyah@student.demo"
        ability = ABILITY_OVERRIDES.get(s.full_name, min(0.9, max(0.35, rng.gauss(0.66, 0.12))))
        subject_noise: dict[str, float] = {}
        for key, topic in topics.items():
            pool = pools[key]
            if not pool:
                continue
            if is_demo and key in AISYAH_SKIP:
                continue
            if not is_demo and rng.random() > 0.85:
                continue
            noise = subject_noise.setdefault(topic.subject_id, rng.gauss(0, 0.07))
            offset = TOPIC_OFFSET.get(key, 0.02) + noise
            if is_demo:
                offset = AISYAH_TARGETS.get(key, 0.7) - ability
            sessions = 2 if is_demo else rng.randint(1, 3)
            days = sorted(rng.sample(range(1, 28), sessions), reverse=True)
            for n, days_ago in enumerate(days):
                start = now - timedelta(days=days_ago, hours=rng.randint(0, 10), minutes=rng.randint(0, 59))
                chosen = rng.sample(pool, min(10, len(pool)))
                qs = QuestionSet(kind="quiz", title=f"{topic.name} — Knowledge Check", owner_id=s.id, subject_id=topic.subject_id,
                                 topic_id=topic.id, status="completed", created_at=start, completed_at=start + timedelta(minutes=8))
                qs.items = [QuestionSetQuestion(question_id=q.id, position=i, marks=q.marks) for i, q in enumerate(chosen)]
                db.add(qs)
                db.flush()
                correct = 0
                if is_demo:
                    target = round((ability + offset) * len(chosen))
                    outcomes = [i < target for i in range(len(chosen))]
                    rng.shuffle(outcomes)
                for i, q in enumerate(chosen):
                    p = min(0.97, max(0.05, ability + offset + DIFF_ADJ[q.difficulty] + 0.04 * n))
                    ok = outcomes[i] if is_demo else rng.random() < p
                    correct += ok
                    answer = q.correct_answer if ok else _wrong_answer(q, rng)
                    db.add(QuestionAttempt(student_id=s.id, question_id=q.id, topic_id=q.topic_id, subject_id=q.subject_id, set_id=qs.id,
                                           answer=answer, is_correct=ok, difficulty=q.difficulty, context="quiz",
                                           time_spent_sec=rng.randint(20, 120), created_at=start + timedelta(seconds=45 * i)))
                    s.xp += gamification.xp_for_answer(q.difficulty, ok)
                s.xp += gamification.XP_QUIZ_COMPLETE
                qs.result = {
                    "set_id": qs.id,
                    "topic": {"id": topic.id, "name": topic.name, "subject_id": topic.subject_id},
                    "percentage": round(correct / len(chosen) * 100, 1),
                    "score": correct,
                    "total": len(chosen),
                    "streak": 0,
                    "next_topic": None,
                }
            if lessons.get(key):
                db.add(LessonProgress(student_id=s.id, lesson_id=lessons[key].id, current_slide=len(lessons[key].slides) - 1, completed=True))
            db.flush()
            progress = recompute_topic(db, s.id, topic.id)
            progress.quizzes_completed = sessions

        if is_demo:
            db.add(LessonProgress(student_id=s.id, lesson_id=lessons["statistics"].id, current_slide=2, completed=False))
            s.current_streak, s.longest_streak, s.last_active_date = 7, 9, today - timedelta(days=1)
        else:
            s.current_streak = rng.randint(0, 6)
            s.longest_streak = s.current_streak + rng.randint(0, 6)
            s.last_active_date = today - timedelta(days=rng.randint(0, 3))
        db.flush()
        gamification.award_badges(db, s)


def _wrong_answer(q: Question, rng: random.Random) -> str:
    if q.question_type == "mcq":
        return rng.choice([o["key"] for o in q.options if o["key"] != q.correct_answer])
    try:
        return str(int(float(q.correct_answer.split("|")[0])) + rng.choice([-2, -1, 1, 2]))
    except ValueError:
        return "not sure"


def _community(db: Session, rng, school, students, teachers, subjects, topics) -> None:
    by_name = {s.full_name.split()[0]: s for s in students}
    now = utcnow()
    student_posts = [
        ("Amir", "MATH", "quadratic", "How do I solve this quadratic equation?", "I don't understand how (x + 2)(x + 3) becomes x² + 5x + 6. Can someone explain the expanding step?", 2,
         [("Sarah", "Multiply each term in the first bracket by each term in the second: x·x + x·3 + 2·x + 2·3 = x² + 5x + 6. Some people remember it as FOIL!"), ("Ali", "Try it backwards too: find two numbers that multiply to 6 and add to 5. That's how you factorise.")]),
        ("Arjun", "PHY", "electricity", "Why does resistance go DOWN in parallel?", "Adding more resistors should add more resistance right? But in parallel the total gets smaller. Confused 😅", 20,
         [("Daniel", "Think of it like adding more lanes on a highway — more paths for the current, so it's easier for charge to flow."), ("Priya", "The formula 1/R = 1/R₁ + 1/R₂ shows it too. Adding more terms makes 1/R bigger, so R smaller.")]),
        ("Mei", "HIST", "independence", "Tips for memorising Sejarah dates?", "There are so many dates for Merdeka and Malaysia. How do you all remember them?", 30,
         [("Nurul", "I make a timeline poster: 1946 → 1948 → 1957 → 1963 → 1965. Seeing it daily helps!")]),
        ("Nurul", "CHEM", "bonding", "Study group for Chemical Bonding this Friday?", "Anyone want to revise ionic vs covalent bonds together at the library after school?", 50, []),
        ("Kevin", "MATH", "functions", "fg(x) vs gf(x) — which one first?", "I always mix up the order for composite functions. Which function do I apply first in fg(x)?", 70,
         [("Sarah", "Inside first! fg(x) = f(g(x)), so do g first, then f.")]),
    ]
    for author, subj, topic, title, body, hours, comments in student_posts:
        post = Post(author_id=by_name[author].id, space="student", school_id=school.id, subject_id=subjects[subj].id, topic_id=topics[topic].id,
                    title=title, body=body, created_at=now - timedelta(hours=hours), comment_count=len(comments))
        db.add(post)
        db.flush()
        for i, (c_author, c_body) in enumerate(comments):
            db.add(Comment(post_id=post.id, author_id=by_name[c_author].id, body=c_body, created_at=post.created_at + timedelta(minutes=20 * (i + 1))))
        voters = rng.sample(students, rng.randint(3, 12))
        for v in voters:
            db.add(PostVote(post_id=post.id, user_id=v.id, value=1))
        post.score = len(voters)

    teacher_posts = [
        ("rohana", "MATH", "Student misconceptions", "What are your students struggling with most in Form 4 Algebra?", "In my classes, many students drop the negative sign when factorising quadratics. What patterns are you seeing?", 5,
         [("farid", "Same here — especially with c < 0. I now make them check by expanding every time."), ("lim", "Ours struggle with forming the equation from word problems more than solving it.")]),
        ("tan", "PHY", "Lesson ideas", "Hands-on activity ideas for Ohm's law", "I'm planning a lab where students build series and parallel circuits with bulbs. Any tips for making it work with limited equipment?", 26,
         [("lim", "PhET simulations work well as a backup if you don't have enough multimeters.")]),
        ("farid", "MATH", "Exam preparation", "Using randomised practice sets before the trial exam", "I've started generating 20-question mixed sets from the question bank each week. Students like that every set is different. Anyone tried something similar?", 48, []),
    ]
    for key, subj, cat, title, body, hours, comments in teacher_posts:
        post = Post(author_id=teachers[key].id, space="teacher", subject_id=subjects[subj].id, category=cat, title=title, body=body,
                    created_at=now - timedelta(hours=hours), comment_count=len(comments))
        db.add(post)
        db.flush()
        for i, (c_author, c_body) in enumerate(comments):
            db.add(Comment(post_id=post.id, author_id=teachers[c_author].id, body=c_body, created_at=post.created_at + timedelta(hours=i + 1)))
        voters = [t for t in teachers.values() if t.id != post.author_id]
        for v in voters:
            db.add(PostVote(post_id=post.id, user_id=v.id, value=1))
        post.score = len(voters)
    db.flush()


def _assignment(db: Session, teacher: Profile, klass: SchoolClass, subject: Subject, topic: Topic) -> None:
    student_ids = list(db.scalars(select(ClassStudent.student_id).where(ClassStudent.class_id == klass.id)))
    weak = [
        p.student_id for p in db.scalars(
            select(StudentTopicProgress).where(StudentTopicProgress.topic_id == topic.id, StudentTopicProgress.student_id.in_(student_ids), StudentTopicProgress.mastery < 55)
        )
    ]
    if not weak:
        return
    pool = sorted(db.scalars(select(Question).where(Question.topic_id == topic.id)), key=lambda q: q.id)
    chosen = random.Random(7).sample(pool, min(8, len(pool)))
    qset = QuestionSet(kind="assignment", title="Quadratic Equations Booster", owner_id=teacher.id, subject_id=subject.id, topic_id=topic.id, seed=7, status="saved")
    qset.items = [QuestionSetQuestion(question_id=q.id, position=i) for i, q in enumerate(chosen)]
    db.add(qset)
    db.flush()
    a = Assignment(teacher_id=teacher.id, title="Quadratic Equations Booster", instructions="Short practice set on factorisation and solving. Try without hints first!",
                   subject_id=subject.id, topic_id=topic.id, set_id=qset.id, due_date=gamification.today_my() + timedelta(days=5))
    db.add(a)
    db.flush()
    for sid in weak:
        db.add(AssignmentStudent(assignment_id=a.id, student_id=sid))
        db.add(Notification(user_id=sid, kind="assignment", title=f"New practice from {teacher.full_name}", body=a.title, link=f"/practice/set/{qset.id}"))
