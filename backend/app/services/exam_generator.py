"""Teacher exam generation from the shared question bank."""

import random
from dataclasses import dataclass, field

from ..models import Question
from .randomizer import DIFFICULTY_ORDER, allocate

DIFFICULTIES = ("easy", "medium", "hard")


@dataclass
class GeneratedExam:
    questions: list[Question]
    marks: dict[str, int]
    seed: int
    warnings: list[str] = field(default_factory=list)
    difficulty_counts: dict[str, int] = field(default_factory=dict)


def generate_exam(
    pool: list[Question],
    num_questions: int,
    difficulty_mix: dict[str, float],
    total_marks: int | None,
    seed: int,
) -> GeneratedExam:
    rng = random.Random(seed)
    pool = sorted(pool, key=lambda q: q.id)
    warnings: list[str] = []
    target = allocate(num_questions, {d: difficulty_mix.get(d, 0) for d in DIFFICULTIES})

    chosen: list[Question] = []
    for d in DIFFICULTIES:
        bucket = [q for q in pool if q.difficulty == d]
        take = min(target[d], len(bucket))
        if take < target[d]:
            warnings.append(f"Only {len(bucket)} {d} questions match your filters (wanted {target[d]}).")
        chosen.extend(rng.sample(bucket, take))

    shortfall = num_questions - len(chosen)
    if shortfall > 0:
        chosen_ids = {q.id for q in chosen}
        leftovers = [q for q in pool if q.id not in chosen_ids]
        fill = rng.sample(leftovers, min(shortfall, len(leftovers)))
        chosen.extend(fill)
        if fill:
            warnings.append(f"Filled {len(fill)} slot(s) with other difficulties to reach the question count.")
        if len(chosen) < num_questions:
            warnings.append(f"Only {len(chosen)} questions available for these filters.")

    chosen.sort(key=lambda q: (DIFFICULTY_ORDER.get(q.difficulty, 1), q.topic_id, q.id))
    return GeneratedExam(
        questions=chosen,
        marks=assign_marks(chosen, total_marks),
        seed=seed,
        warnings=warnings,
        difficulty_counts={d: sum(1 for q in chosen if q.difficulty == d) for d in DIFFICULTIES},
    )


def assign_marks(questions: list[Question], total_marks: int | None) -> dict[str, int]:
    """Scale each question's base marks so they sum to total_marks (min 1 each)."""
    base = {q.id: max(q.marks, 1) for q in questions}
    if not total_marks or not questions:
        return base
    if total_marks < len(questions):
        total_marks = len(questions)
    extra = allocate(total_marks - len(questions), {qid: m for qid, m in base.items()})
    return {qid: 1 + extra[qid] for qid in base}


def pick_replacement(pool: list[Question], current: Question, exclude_ids: set[str], seed: int) -> Question | None:
    candidates = [q for q in sorted(pool, key=lambda q: q.id) if q.id not in exclude_ids]
    if not candidates:
        return None
    rng = random.Random(seed)
    for match in (
        lambda q: q.difficulty == current.difficulty and q.topic_id == current.topic_id,
        lambda q: q.difficulty == current.difficulty,
        lambda q: True,
    ):
        subset = [q for q in candidates if match(q)]
        if subset:
            return rng.choice(subset)
    return None
