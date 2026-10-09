"""Deterministic topic-mastery calculation.

mastery = evidence * (0.7 * recent + 0.3 * historical)

* recent      = difficulty-weighted accuracy over the latest RECENT_WINDOW attempts
* historical  = difficulty-weighted accuracy over all older attempts
                (when there is no history, recent is used on its own)
* evidence    = 0.5 + 0.5 * min(1, attempts / RECENT_WINDOW), so that a couple
                of lucky answers cannot mark a topic as mastered.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

RECENT_WINDOW = 10
RECENT_WEIGHT = 0.7
HISTORICAL_WEIGHT = 0.3
DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}

LEVELS = [
    (80, "mastered", "Mastered"),
    (60, "good", "Good"),
    (40, "developing", "Developing"),
    (0, "needs_attention", "Needs Attention"),
]


class AttemptLike(Protocol):
    is_correct: bool
    difficulty: str
    created_at: datetime


@dataclass(frozen=True)
class MasteryResult:
    mastery: float
    recent_score: float
    historical_score: float | None
    attempts: int
    correct: int


def weighted_accuracy(attempts: Sequence[AttemptLike]) -> float:
    total = sum(DIFFICULTY_WEIGHT.get(a.difficulty, 1.0) for a in attempts)
    if total == 0:
        return 0.0
    earned = sum(DIFFICULTY_WEIGHT.get(a.difficulty, 1.0) for a in attempts if a.is_correct)
    return earned / total * 100


def compute_mastery(attempts: Sequence[AttemptLike]) -> MasteryResult:
    ordered = sorted(attempts, key=lambda a: a.created_at)
    if not ordered:
        return MasteryResult(0.0, 0.0, None, 0, 0)
    recent = ordered[-RECENT_WINDOW:]
    history = ordered[:-RECENT_WINDOW]
    recent_score = weighted_accuracy(recent)
    historical_score = weighted_accuracy(history) if history else None
    blended = (
        RECENT_WEIGHT * recent_score + HISTORICAL_WEIGHT * historical_score
        if historical_score is not None
        else recent_score
    )
    evidence = 0.5 + 0.5 * min(1.0, len(ordered) / RECENT_WINDOW)
    return MasteryResult(
        mastery=round(blended * evidence, 1),
        recent_score=round(recent_score, 1),
        historical_score=round(historical_score, 1) if historical_score is not None else None,
        attempts=len(ordered),
        correct=sum(1 for a in ordered if a.is_correct),
    )


def mastery_level(mastery: float, attempts: int = 1) -> dict:
    if attempts == 0:
        return {"key": "not_started", "label": "Not Started"}
    for threshold, key, label in LEVELS:
        if mastery >= threshold:
            return {"key": key, "label": label}
    return {"key": "needs_attention", "label": "Needs Attention"}
