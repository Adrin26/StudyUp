from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.models import Question
from app.services.exam_generator import assign_marks, generate_exam
from app.services.grading import is_correct
from app.services.mastery import compute_mastery, mastery_level
from app.services.randomizer import allocate, sample, select_for_quiz


@dataclass
class A:
    is_correct: bool
    difficulty: str
    created_at: datetime


def attempts(pattern: str, difficulty="medium"):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [A(c == "1", difficulty, base + timedelta(minutes=i)) for i, c in enumerate(pattern)]


def test_mastery_empty():
    assert compute_mastery([]).mastery == 0


def test_mastery_recent_weighted_more_than_history():
    improving = compute_mastery(attempts("0" * 10 + "1" * 10))
    declining = compute_mastery(attempts("1" * 10 + "0" * 10))
    assert improving.mastery == 70.0
    assert declining.mastery == 30.0


def test_mastery_needs_evidence():
    assert compute_mastery(attempts("11")).mastery == 60.0
    assert compute_mastery(attempts("1" * 10)).mastery == 100.0


def test_mastery_difficulty_weighting():
    mixed = attempts("10") 
    mixed[0].difficulty, mixed[1].difficulty = "hard", "easy"
    assert compute_mastery(mixed).recent_score == round(2 / 3 * 100, 1)


def test_mastery_levels():
    assert mastery_level(85)["key"] == "mastered"
    assert mastery_level(65)["key"] == "good"
    assert mastery_level(45)["key"] == "developing"
    assert mastery_level(10)["key"] == "needs_attention"
    assert mastery_level(0, attempts=0)["key"] == "not_started"


def test_allocate_largest_remainder():
    assert allocate(40, {"easy": 20, "medium": 50, "hard": 30}) == {"easy": 8, "medium": 20, "hard": 12}
    assert sum(allocate(7, {"a": 1, "b": 1, "c": 1}).values()) == 7


def test_sample_is_deterministic_and_order_independent():
    items = [f"q{i}" for i in range(50)]
    first = sample(items, 10, seed=42, key=str)
    assert first == sample(list(reversed(items)), 10, seed=42, key=str)
    assert first != sample(items, 10, seed=43, key=str)


def test_quiz_selection_prefers_unseen_and_orders_by_difficulty():
    pool = [{"id": f"q{i}", "d": ["easy", "medium", "hard"][i % 3]} for i in range(15)]
    mastered = {f"q{i}" for i in range(10)}
    chosen = select_for_quiz(pool, 5, 1, key=lambda q: q["id"], mastered_ids=mastered, difficulty=lambda q: q["d"])
    assert {q["id"] for q in chosen} == {f"q{i}" for i in range(10, 15)}
    order = {"easy": 0, "medium": 1, "hard": 2}
    assert [order[q["d"]] for q in chosen] == sorted(order[q["d"]] for q in chosen)


def _q(i, difficulty, marks=1):
    return Question(id=f"id{i:03d}", subject_id="s", topic_id=f"t{i % 3}", question_text="?", difficulty=difficulty, marks=marks, correct_answer="A")


def test_exam_generation_respects_mix_and_marks():
    pool = [_q(i, d) for i, d in enumerate(["easy"] * 20 + ["medium"] * 20 + ["hard"] * 20)]
    exam = generate_exam(pool, 10, {"easy": 20, "medium": 50, "hard": 30}, total_marks=25, seed=9)
    assert exam.difficulty_counts == {"easy": 2, "medium": 5, "hard": 3}
    assert sum(exam.marks.values()) == 25
    assert not exam.warnings


def test_exam_generation_fills_shortfall_with_warning():
    pool = [_q(i, "easy") for i in range(10)] + [_q(100, "hard")]
    exam = generate_exam(pool, 6, {"easy": 0, "medium": 50, "hard": 50}, None, seed=1)
    assert len(exam.questions) == 6
    assert exam.warnings


def test_assign_marks_minimum_one():
    qs = [_q(i, "easy", marks=m) for i, m in enumerate([1, 2, 3])]
    marks = assign_marks(qs, 3)
    assert marks == {q.id: 1 for q in qs}


def test_grading_short_answer_numeric_and_minus_sign():
    q = Question(question_type="short_answer", correct_answer="-2", difficulty="easy")
    assert is_correct(q, "−2")
    assert is_correct(q, " -2.00 ")
    assert not is_correct(q, "2")
    mc = Question(question_type="mcq", correct_answer="B", difficulty="easy")
    assert is_correct(mc, "b") and not is_correct(mc, "C")
