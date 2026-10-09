"""Deterministic, seed-based question selection.

Given the same pool and seed, selection is always reproducible, which makes
practice sets shareable and exams auditable. The AI is never involved.
"""

import random
import secrets
from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")

DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def new_seed() -> int:
    return secrets.randbelow(2**31 - 1)


def sample(pool: Sequence[T], n: int, seed: int, key: Callable[[T], str]) -> list[T]:
    """Pick up to n items. Pool is sorted by key first so DB ordering can't change results."""
    ordered = sorted(pool, key=key)
    rng = random.Random(seed)
    return rng.sample(ordered, min(n, len(ordered)))


def select_for_quiz(
    pool: Sequence[T],
    n: int,
    seed: int,
    key: Callable[[T], str],
    mastered_ids: set[str],
    difficulty: Callable[[T], str],
) -> list[T]:
    """Prefer questions the student hasn't answered correctly yet, then order easy → hard."""
    ordered = sorted(pool, key=key)
    rng = random.Random(seed)
    fresh = [q for q in ordered if key(q) not in mastered_ids]
    seen = [q for q in ordered if key(q) in mastered_ids]
    rng.shuffle(fresh)
    rng.shuffle(seen)
    chosen = (fresh + seen)[:n]
    return sorted(chosen, key=lambda q: DIFFICULTY_ORDER.get(difficulty(q), 1))


def allocate(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split an integer total across weights with the largest-remainder method."""
    weight_sum = sum(w for w in weights.values() if w > 0)
    if total <= 0 or weight_sum <= 0:
        return {k: 0 for k in weights}
    raw = {k: total * max(w, 0) / weight_sum for k, w in weights.items()}
    counts = {k: int(v) for k, v in raw.items()}
    remainder = total - sum(counts.values())
    for k in sorted(raw, key=lambda k: (-(raw[k] - counts[k]), k))[:remainder]:
        counts[k] += 1
    return counts
