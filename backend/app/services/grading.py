"""Deterministic answer checking (never delegated to the LLM)."""

import re

from ..models import Question

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def normalise(text: str) -> str:
    text = text.strip().lower().replace("−", "-")
    text = re.sub(r"\s+", "", text)
    return text.rstrip(".")


def is_correct(question: Question, answer: str) -> bool:
    if answer is None:
        return False
    if question.question_type == "mcq":
        return answer.strip().upper() == question.correct_answer.strip().upper()
    given = normalise(answer)
    accepted = [normalise(a) for a in question.correct_answer.split("|")]
    if given in accepted:
        return True
    if _NUMBER.match(given):
        for a in accepted:
            if _NUMBER.match(a) and abs(float(a) - float(given)) <= 0.01:
                return True
    return False


def display_answer(question: Question) -> str:
    if question.question_type == "mcq" and question.options:
        for opt in question.options:
            if opt["key"] == question.correct_answer:
                return f"{opt['key']}. {opt['text']}"
    return question.correct_answer.split("|")[0]


def display_given(question: Question, answer: str) -> str:
    if question.question_type == "mcq" and question.options:
        for opt in question.options:
            if opt["key"] == answer.strip().upper():
                return f"{opt['key']}. {opt['text']}"
    return answer
