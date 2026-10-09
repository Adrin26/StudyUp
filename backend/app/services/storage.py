"""File storage behind one interface.

Development stores files on local disk. Public files (question images) are
served from /uploads; private files (memo attachments) live in a separate
directory and are only returned by endpoints that check permissions.
A Supabase Storage implementation can replace these functions later without changing callers.
The service-role key is never read here and is never sent to the frontend.
"""

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from ..config import get_settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_PRIVATE_KEY = re.compile(r"^private/([0-9a-f]{32}-[A-Za-z0-9._-]+)$")
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}
FILE_TYPES = IMAGE_TYPES | {"application/pdf": ".pdf"}


def _matches_type(data: bytes, content_type: str) -> bool:
    """The browser-reported type is only a claim; check the file's leading bytes as well."""
    if content_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/gif":
        return data.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if content_type == "application/pdf":
        return data.startswith(b"%PDF-")
    return False


def _dir(private: bool) -> Path:
    s = get_settings()
    root = Path(s.private_upload_dir if private else s.upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save(data: bytes, filename: str, content_type: str, *, images_only: bool = False, max_bytes: int = 2_000_000, private: bool = False) -> str:
    allowed = IMAGE_TYPES if images_only else FILE_TYPES
    if content_type not in allowed:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "That file type is not allowed")
    if len(data) > max_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File is too large")
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File is empty")
    if not _matches_type(data, content_type):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "The file's contents do not match its type")
    stem = _SAFE.sub("-", Path(filename).stem)[:40] or "file"
    key = f"{uuid.uuid4().hex}-{stem}{allowed[content_type]}"
    (_dir(private) / key).write_bytes(data)
    return f"private/{key}" if private else f"/uploads/{key}"


def path_for(storage_key: str) -> Path | None:
    """Disk path of a stored file, or None if the key is malformed or the file is gone."""
    if match := _PRIVATE_KEY.match(storage_key):
        path = _dir(True) / match.group(1)
    elif storage_key.startswith("/uploads/") and _SAFE.sub("", storage_key[9:]) == storage_key[9:]:
        path = _dir(False) / storage_key[9:]
    else:
        return None
    return path if path.is_file() else None
