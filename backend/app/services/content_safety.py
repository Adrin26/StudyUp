"""Text checks for community posts and comments.

The student community rejects links and personal contact details outright; the teacher
community allows ordinary http(s) links but never script or data URLs.
"""

import re

from fastapi import HTTPException, status

_URL = re.compile(r"(https?://|www\.)\S+|\b[\w-]+\.(com|net|org|my|io|ly|me|xyz|info|co)(/\S*)?\b", re.IGNORECASE)
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(\+?6?0)?1\d[\s-]?\d{3,4}[\s-]?\d{4}\b")
_UNSAFE_SCHEME = re.compile(r"\b(javascript|data|vbscript|file):", re.IGNORECASE)


def check_text(text: str, space: str) -> None:
    if _UNSAFE_SCHEME.search(text):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "This link type is not allowed")
    if space != "student":
        return
    if _EMAIL.search(text) or _PHONE.search(text):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Please don't share email addresses or phone numbers in the student community")
    if _URL.search(text):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Links aren't allowed in the student community")
