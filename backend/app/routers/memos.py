"""School memos. Admins draft and publish; everyone else only sees memos that are live for them.
Attachments are private files, downloaded through an endpoint that applies the same rule."""

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MemoAcknowledgement, MemoAttachment, MemoRead, Notification, Profile, SchoolMemo, utcnow
from ..permissions import require_admin
from ..schemas import MemoIn, StatusIn
from ..security import get_current_user
from ..services import audit, storage

router = APIRouter(tags=["memos"])


def _memo(db: Session, memo_id: str, admin: Profile) -> SchoolMemo:
    memo = db.get(SchoolMemo, memo_id)
    if memo is None or memo.school_id != admin.school_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    return memo


def _live(memo: SchoolMemo, user: Profile) -> bool:
    now = utcnow()
    if memo.school_id != user.school_id or memo.status != "published":
        return False
    if memo.publish_at and memo.publish_at > now:
        return False
    if memo.expires_at and memo.expires_at <= now:
        return False
    if memo.audience == "teachers" and user.role == "student":
        return False
    if memo.audience == "students" and user.role == "teacher":
        return False
    return True


def _out(db: Session, memo: SchoolMemo, user: Profile | None = None) -> dict:
    reads = db.scalar(select(func.count()).select_from(MemoRead).where(MemoRead.memo_id == memo.id)) or 0
    acks = db.scalar(select(func.count()).select_from(MemoAcknowledgement).where(MemoAcknowledgement.memo_id == memo.id)) or 0
    mine_read = mine_ack = False
    if user:
        mine_read = db.get(MemoRead, (memo.id, user.id)) is not None
        mine_ack = db.get(MemoAcknowledgement, (memo.id, user.id)) is not None
    return {
        "id": memo.id, "title": memo.title, "body": memo.body, "audience": memo.audience, "status": memo.status,
        "publish_at": memo.publish_at, "expires_at": memo.expires_at,
        "requires_acknowledgement": memo.requires_acknowledgement,
        "created_at": memo.created_at, "read_count": reads, "acknowledgement_count": acks,
        "read": mine_read, "acknowledged": mine_ack,
        "attachments": [{"id": a.id, "filename": a.filename, "url": f"/api/memos/{memo.id}/attachments/{a.id}"} for a in memo.attachments],
    }


def _csv_cell(value: str) -> str:
    # Spreadsheet apps run cells starting with these characters as formulas.
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _notify(db: Session, memo: SchoolMemo) -> None:
    roles = {"teachers": ["teacher", "admin"], "students": ["student"], "all": ["admin", "teacher", "student"]}[memo.audience]
    people = db.scalars(select(Profile).where(Profile.school_id == memo.school_id, Profile.status == "active", Profile.role.in_(roles)))
    for person in people:
        db.add(Notification(user_id=person.id, kind="memo", title=memo.title, body="A new school memo was published.", link=f"/memos/{memo.id}"))


@router.get("/api/admin/memos")
def admin_list(admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(SchoolMemo).where(SchoolMemo.school_id == admin.school_id).order_by(SchoolMemo.created_at.desc()))
    return [_out(db, m) for m in rows]


@router.post("/api/admin/memos", status_code=status.HTTP_201_CREATED)
def create_memo(body: MemoIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = SchoolMemo(school_id=admin.school_id, title=body.title.strip(), body=body.body.strip(), audience=body.audience,
                      requires_acknowledgement=body.requires_acknowledgement, publish_at=body.publish_at, expires_at=body.expires_at,
                      created_by=admin.id, status="draft")
    db.add(memo)
    db.flush()
    audit.record(db, "memo.create", "memo", memo.id, actor=admin, request=request, details={"title": memo.title})
    db.commit()
    db.refresh(memo)
    return _out(db, memo)


@router.patch("/api/admin/memos/{memo_id}")
def update_memo(memo_id: str, body: MemoIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = _memo(db, memo_id, admin)
    if memo.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived memos cannot be edited")
    memo.title, memo.body, memo.audience = body.title.strip(), body.body.strip(), body.audience
    memo.requires_acknowledgement = body.requires_acknowledgement
    memo.publish_at, memo.expires_at = body.publish_at, body.expires_at
    audit.record(db, "memo.update", "memo", memo.id, actor=admin, request=request, details={"title": memo.title})
    db.commit()
    return _out(db, memo)


@router.post("/api/admin/memos/{memo_id}/status")
def set_status(memo_id: str, body: StatusIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = _memo(db, memo_id, admin)
    was = memo.status
    memo.status = body.status
    if body.status == "published" and memo.publish_at is None:
        memo.publish_at = utcnow()
    if body.status == "published" and was != "published":
        _notify(db, memo)
    audit.record(db, "memo.status", "memo", memo.id, actor=admin, request=request, details={"status": memo.status})
    db.commit()
    return _out(db, memo)


@router.post("/api/admin/memos/{memo_id}/attachments", status_code=status.HTTP_201_CREATED)
async def add_attachment(memo_id: str, request: Request, file: UploadFile = File(...), admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = _memo(db, memo_id, admin)
    if memo.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived memos cannot be edited")
    if len(memo.attachments) >= 5:
        raise HTTPException(status.HTTP_409_CONFLICT, "A memo can have at most 5 attachments")
    key = storage.save(await file.read(), file.filename or "file", file.content_type or "", max_bytes=5_000_000, private=True)
    filename = (file.filename or "file")[:200]
    db.add(MemoAttachment(memo_id=memo.id, filename=filename, content_type=file.content_type or "application/octet-stream", storage_key=key))
    audit.record(db, "memo.attachment_add", "memo", memo.id, actor=admin, request=request, details={"filename": filename})
    db.commit()
    db.refresh(memo)
    return _out(db, memo)


@router.delete("/api/admin/memos/{memo_id}/attachments/{attachment_id}")
def remove_attachment(memo_id: str, attachment_id: str, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = _memo(db, memo_id, admin)
    attachment = db.get(MemoAttachment, attachment_id)
    if attachment is None or attachment.memo_id != memo.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    if memo.status == "archived":
        raise HTTPException(status.HTTP_409_CONFLICT, "Archived memos cannot be edited")
    path = storage.path_for(attachment.storage_key)
    memo.attachments.remove(attachment)
    audit.record(db, "memo.attachment_remove", "memo", memo.id, actor=admin, request=request, details={"filename": attachment.filename})
    db.commit()
    if path:
        path.unlink(missing_ok=True)
    db.refresh(memo)
    return _out(db, memo)


@router.get("/api/memos/{memo_id}/attachments/{attachment_id}")
def download_attachment(memo_id: str, attachment_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    memo = db.get(SchoolMemo, memo_id)
    is_school_admin = memo is not None and user.role == "admin" and memo.school_id == user.school_id
    if memo is None or not (is_school_admin or _live(memo, user)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    attachment = db.get(MemoAttachment, attachment_id)
    path = storage.path_for(attachment.storage_key) if attachment and attachment.memo_id == memo.id else None
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.filename)


@router.get("/api/admin/memos/{memo_id}/acknowledgements")
def acknowledgement_report(memo_id: str, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    memo = _memo(db, memo_id, admin)
    roles = {"teachers": ["teacher"], "students": ["student"], "all": ["teacher", "student"]}[memo.audience]
    people = db.scalars(select(Profile).where(Profile.school_id == admin.school_id, Profile.role.in_(roles), Profile.status == "active").order_by(Profile.full_name))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["name", "email", "role", "read", "acknowledged"])
    for person in people:
        read = db.get(MemoRead, (memo.id, person.id))
        ack = db.get(MemoAcknowledgement, (memo.id, person.id))
        writer.writerow([_csv_cell(person.full_name), _csv_cell(person.email), person.role, "yes" if read else "no", "yes" if ack else "no"])
    return PlainTextResponse(out.getvalue(), media_type="text/csv")


@router.get("/api/memos")
def inbox(user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SchoolMemo).where(SchoolMemo.school_id == user.school_id, SchoolMemo.status == "published").order_by(SchoolMemo.publish_at.desc()))
    return [_out(db, m, user) for m in rows if _live(m, user)]


@router.get("/api/memos/{memo_id}")
def detail(memo_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    memo = db.get(SchoolMemo, memo_id)
    if memo is None or not _live(memo, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    if db.get(MemoRead, (memo.id, user.id)) is None:
        db.add(MemoRead(memo_id=memo.id, user_id=user.id))
        db.commit()
    return _out(db, memo, user)


@router.post("/api/memos/{memo_id}/acknowledge")
def acknowledge(memo_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    memo = db.get(SchoolMemo, memo_id)
    if memo is None or not _live(memo, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Memo not found")
    if not memo.requires_acknowledgement:
        raise HTTPException(status.HTTP_409_CONFLICT, "This memo does not ask for an acknowledgement")
    if db.get(MemoRead, (memo.id, user.id)) is None:
        db.add(MemoRead(memo_id=memo.id, user_id=user.id))
    if db.get(MemoAcknowledgement, (memo.id, user.id)) is None:
        db.add(MemoAcknowledgement(memo_id=memo.id, user_id=user.id))
    db.commit()
    return _out(db, memo, user)
