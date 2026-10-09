"""Teacher and student discussion spaces.

Visibility rules, all enforced here:
- teacher space: teachers and admins of any school; students never.
- student space: members (any role) of the school the post belongs to; only students post, comment and vote.
- hidden content: only its author and the moderators of that content can see it.
- moderators are the admins of the school that owns the content (the post's school in the
  student space, the author's school in the teacher space).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Comment, ContentReport, Notification, Post, PostBookmark, PostVote, Profile, utcnow
from ..schemas import CommentIn, ModerationIn, PostIn, ReportIn, VoteIn
from ..permissions import require_admin
from ..security import get_current_user
from ..services import audit
from ..services.content_safety import check_text
from ..services.question_bank import names_lookup
from ..services.rate_limit import limiter

router = APIRouter(prefix="/api/community", tags=["community"])

TEACHER_CATEGORIES = [
    "Difficult questions", "Teaching strategies", "Exam preparation", "Lesson ideas", "Student misconceptions",
    "Question quality", "Classroom management", "Resources and materials",
]
REPORT_REASONS = {
    "spam": "Spam", "inappropriate": "Inappropriate", "bullying": "Bullying or harassment",
    "personal_info": "Personal information", "off_topic": "Not about learning", "other": "Other",
}
AUTO_HIDE_REPORTS = 3
LIMITS = {"post": (5, 600), "comment": (20, 600), "vote": (60, 60), "report": (10, 3600)}


def _throttle(user: Profile, action: str) -> None:
    limit, window = LIMITS[action]
    key = f"community:{action}:{user.id}"
    if limiter.blocked(key, limit, window):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "You're doing that too often. Please wait a few minutes.")
    limiter.hit(key)


def _can_read(user: Profile, space: str, school_id: str | None) -> bool:
    if space == "teacher":
        return user.role in ("teacher", "admin")
    return user.school_id is not None and user.school_id == school_id


def _can_write(user: Profile, space: str) -> bool:
    return (space == "student" and user.role == "student") or (space == "teacher" and user.role in ("teacher", "admin"))


def _content_school(db: Session, post: Post) -> str | None:
    if post.space == "student":
        return post.school_id
    author = db.get(Profile, post.author_id)
    return author.school_id if author else None


def _is_moderator(db: Session, user: Profile, post: Post) -> bool:
    return user.role == "admin" and user.school_id is not None and user.school_id == _content_school(db, post)


def _get_post(db: Session, post_id: str, user: Profile) -> Post:
    post = db.get(Post, post_id)
    if post is None or not _can_read(user, post.space, post.school_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    if post.status == "hidden" and post.author_id != user.id and not _is_moderator(db, user, post):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


def _get_comment(db: Session, comment_id: str, user: Profile) -> tuple[Comment, Post]:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    post = _get_post(db, comment.post_id, user)
    if comment.status == "hidden" and comment.author_id != user.id and not _is_moderator(db, user, post):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
    return comment, post


def post_link(post: Post, user: Profile) -> str:
    if user.role == "student":
        return f"/community/{post.id}"
    if user.role == "admin":
        return "/admin/moderation"
    return f"/teacher/{'community' if post.space == 'teacher' else 'student-community'}/{post.id}"


def _notify(db: Session, user_id: str, title: str, body: str | None, post: Post) -> None:
    recipient = db.get(Profile, user_id)
    if recipient:
        db.add(Notification(user_id=user_id, kind="community", title=title, body=body, link=post_link(post, recipient)))


def _author(a: Profile) -> dict:
    return {"id": a.id, "name": a.full_name, "role": a.role}


def _post_payload(post: Post, author: Profile, user: Profile, my_vote: int, bookmarked: bool, topics: dict, subjects: dict) -> dict:
    data = {
        "id": post.id,
        "space": post.space,
        "title": post.title,
        "body": post.body,
        "category": post.category,
        "subject_id": post.subject_id,
        "subject": subjects.get(post.subject_id),
        "topic_id": post.topic_id,
        "topic": topics.get(post.topic_id),
        "score": post.score,
        "comment_count": post.comment_count,
        "created_at": post.created_at,
        "author": _author(author),
        "my_vote": my_vote,
        "bookmarked": bookmarked,
        "status": post.status,
    }
    if post.status == "hidden":
        data["moderation_reason"] = post.moderation_reason
    return data


@router.get("/meta")
def meta(user: Profile = Depends(get_current_user)):
    return {
        "teacher_categories": TEACHER_CATEGORIES,
        "report_reasons": [{"value": k, "label": v} for k, v in REPORT_REASONS.items()],
        "can_post_student": user.role == "student",
        "can_post_teacher": user.role in ("teacher", "admin"),
    }


@router.get("/posts")
def list_posts(
    space: str = Query("student", pattern="^(student|teacher)$"),
    subject_id: str | None = None,
    topic_id: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, max_length=100),
    sort: str = Query("new", pattern="^(new|top)$"),
    saved: bool = False,
    page: int = Query(1, ge=1),
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_read(user, space, user.school_id if space == "student" else None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot access this community")
    stmt = (
        select(Post, Profile).join(Profile, Profile.id == Post.author_id)
        .where(Post.space == space, or_(Post.status == "visible", Post.author_id == user.id))
    )
    if space == "student":
        stmt = stmt.where(Post.school_id == user.school_id)
    if saved:
        stmt = stmt.join(PostBookmark, (PostBookmark.post_id == Post.id) & (PostBookmark.user_id == user.id))
    if subject_id:
        stmt = stmt.where(Post.subject_id == subject_id)
    if topic_id:
        stmt = stmt.where(Post.topic_id == topic_id)
    if category:
        stmt = stmt.where(Post.category == category)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Post.title.ilike(like), Post.body.ilike(like)))
    stmt = stmt.order_by(Post.score.desc(), Post.created_at.desc()) if sort == "top" else stmt.order_by(Post.created_at.desc())
    rows = db.execute(stmt.offset((page - 1) * 20).limit(20)).all()
    ids = [p.id for p, _ in rows]
    votes = dict(db.execute(select(PostVote.post_id, PostVote.value).where(PostVote.user_id == user.id, PostVote.post_id.in_(ids))).all()) if ids else {}
    marks = set(db.scalars(select(PostBookmark.post_id).where(PostBookmark.user_id == user.id, PostBookmark.post_id.in_(ids)))) if ids else set()
    topics, subjects = names_lookup(db)
    return [_post_payload(p, a, user, votes.get(p.id, 0), p.id in marks, topics, subjects) for p, a in rows]


@router.post("/posts")
def create_post(body: PostIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _can_write(user, body.space):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot post in this community")
    check_text(f"{body.title}\n{body.body}", body.space)
    _throttle(user, "post")
    post = Post(
        author_id=user.id,
        space=body.space,
        school_id=user.school_id if body.space == "student" else None,
        subject_id=body.subject_id,
        topic_id=body.topic_id,
        category=body.category if body.space == "teacher" and body.category in TEACHER_CATEGORIES else None,
        title=body.title.strip(),
        body=body.body.strip(),
    )
    db.add(post)
    db.commit()
    topics, subjects = names_lookup(db)
    return _post_payload(post, user, user, 0, False, topics, subjects)


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    author = db.get(Profile, post.author_id)
    vote = db.get(PostVote, {"post_id": post.id, "user_id": user.id})
    bookmarked = db.get(PostBookmark, {"post_id": post.id, "user_id": user.id}) is not None
    moderator = _is_moderator(db, user, post)
    stmt = select(Comment, Profile).join(Profile, Profile.id == Comment.author_id).where(Comment.post_id == post.id)
    if not moderator:
        stmt = stmt.where(or_(Comment.status == "visible", Comment.author_id == user.id))
    comments = db.execute(stmt.order_by(Comment.created_at)).all()
    topics, subjects = names_lookup(db)
    can_write = _can_write(user, post.space) and post.status == "visible"
    return {
        **_post_payload(post, author, user, vote.value if vote else 0, bookmarked, topics, subjects),
        "can_comment": can_write,
        "can_vote": can_write and post.author_id != user.id,
        "can_report": post.author_id != user.id and post.status == "visible",
        "can_moderate": moderator,
        "comments": [
            {
                "id": c.id, "parent_id": c.parent_id, "body": c.body, "created_at": c.created_at, "author": _author(a),
                "status": c.status, "moderation_reason": c.moderation_reason if c.status == "hidden" else None,
            }
            for c, a in comments
        ],
    }


@router.post("/posts/{post_id}/comments")
def add_comment(post_id: str, body: CommentIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if not _can_write(user, post.space) or post.status != "visible":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot comment in this community")
    parent = None
    if body.parent_id:
        parent = db.get(Comment, body.parent_id)
        if parent is None or parent.post_id != post.id or parent.status != "visible":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Comment not found")
        if parent.parent_id is not None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Replies can only be one level deep")
    check_text(body.body, post.space)
    _throttle(user, "comment")
    comment = Comment(post_id=post.id, author_id=user.id, parent_id=parent.id if parent else None, body=body.body.strip(), created_at=utcnow())
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    recipients = {post.author_id} | ({parent.author_id} if parent else set())
    for rid in recipients - {user.id}:
        _notify(db, rid, f"{user.full_name} replied", post.title, post)
    db.commit()
    return {"id": comment.id, "parent_id": comment.parent_id, "body": comment.body, "created_at": comment.created_at, "author": _author(user), "status": "visible", "moderation_reason": None}


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(comment_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    comment, post = _get_comment(db, comment_id, user)
    if comment.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own comments")
    removed = 1 + db.scalar(select(func.count()).select_from(Comment).where(Comment.parent_id == comment.id))
    db.delete(comment)
    post.comment_count = max(0, (post.comment_count or 0) - removed)
    db.commit()


@router.post("/posts/{post_id}/vote")
def vote(post_id: str, body: VoteIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if not _can_write(user, post.space) or post.status != "visible":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot vote in this community")
    if post.author_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot vote on your own post")
    _throttle(user, "vote")
    existing = db.get(PostVote, {"post_id": post.id, "user_id": user.id})
    if body.value == 0:
        if existing:
            db.delete(existing)
    elif existing:
        existing.value = body.value
    else:
        db.add(PostVote(post_id=post.id, user_id=user.id, value=body.value))
    db.flush()
    post.score = db.scalar(select(func.coalesce(func.sum(PostVote.value), 0)).where(PostVote.post_id == post.id))
    db.commit()
    return {"score": post.score, "my_vote": body.value}


@router.put("/posts/{post_id}/bookmark", status_code=204)
def bookmark(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if db.get(PostBookmark, {"post_id": post.id, "user_id": user.id}) is None:
        db.add(PostBookmark(post_id=post.id, user_id=user.id))
        db.commit()


@router.delete("/posts/{post_id}/bookmark", status_code=204)
def remove_bookmark(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(PostBookmark, {"post_id": post_id, "user_id": user.id})
    if row:
        db.delete(row)
        db.commit()


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if post.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts; moderators hide posts instead")
    db.delete(post)
    db.commit()


# ---- Reports and moderation ----

def _report(db: Session, user: Profile, post: Post, comment: Comment | None, body: ReportIn) -> dict:
    target_author = comment.author_id if comment else post.author_id
    target_status = comment.status if comment else post.status
    if target_author == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot report your own content")
    if target_status != "visible":
        raise HTTPException(status.HTTP_409_CONFLICT, "This content is already hidden")
    target = ContentReport.comment_id == comment.id if comment else ContentReport.post_id == post.id
    open_reports = select(ContentReport).where(target, ContentReport.status == "open")
    if db.scalar(open_reports.where(ContentReport.reporter_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already reported this")
    _throttle(user, "report")
    school_id = _content_school(db, post)
    db.add(ContentReport(school_id=school_id, reporter_id=user.id, post_id=None if comment else post.id,
                         comment_id=comment.id if comment else None, reason=body.reason, details=body.details))
    db.flush()
    count = db.scalar(select(func.count(func.distinct(ContentReport.reporter_id))).where(target, ContentReport.status == "open"))
    hidden = False
    if count >= AUTO_HIDE_REPORTS:
        item = comment or post
        item.status, item.moderation_reason, item.moderated_at = "hidden", "Hidden automatically after several reports, pending review", utcnow()
        hidden = True
    if count == 1 or hidden:
        admins = db.scalars(select(Profile.id).where(Profile.role == "admin", Profile.school_id == school_id, Profile.status == "active"))
        for aid in admins:
            title = "Reported content was hidden automatically" if hidden else "New community report"
            db.add(Notification(user_id=aid, kind="moderation", title=title, body=post.title, link="/admin/moderation"))
    db.commit()
    return {"reported": True}


@router.post("/posts/{post_id}/report")
def report_post(post_id: str, body: ReportIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    return _report(db, user, _get_post(db, post_id, user), None, body)


@router.post("/comments/{comment_id}/report")
def report_comment(comment_id: str, body: ReportIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    comment, post = _get_comment(db, comment_id, user)
    return _report(db, user, post, comment, body)


def _moderate(db: Session, admin: Profile, post: Post, comment: Comment | None, body: ModerationIn, request: Request) -> dict:
    if not _is_moderator(db, admin, post):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only an admin of this school can moderate this content")
    item = comment or post
    target = ContentReport.comment_id == comment.id if comment else ContentReport.post_id == post.id
    kind = "comment" if comment else "post"
    if body.action == "hide":
        item.status, item.moderation_reason = "hidden", (body.reason or "Removed by a moderator").strip()
        report_status = "actioned"
        if item.author_id != admin.id:
            _notify(db, item.author_id, f"Your {kind} was hidden by a moderator", item.moderation_reason, post)
    else:
        if body.action == "restore":
            item.status, item.moderation_reason = "visible", None
        report_status = "dismissed"
    item.moderated_by, item.moderated_at = admin.id, utcnow()
    for r in db.scalars(select(ContentReport).where(target, ContentReport.status == "open")):
        r.status, r.resolved_by, r.resolved_at = report_status, admin.id, utcnow()
    audit.record(db, f"community.{kind}_{body.action}", kind, item.id, actor=admin, school_id=admin.school_id,
                 details={"space": post.space, "reason": body.reason}, request=request)
    db.commit()
    return {"id": item.id, "status": item.status}


@router.post("/posts/{post_id}/moderation")
def moderate_post(post_id: str, body: ModerationIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    return _moderate(db, admin, _get_post(db, post_id, admin), None, body, request)


@router.post("/comments/{comment_id}/moderation")
def moderate_comment(comment_id: str, body: ModerationIn, request: Request, admin: Profile = Depends(require_admin), db: Session = Depends(get_db)):
    comment, post = _get_comment(db, comment_id, admin)
    return _moderate(db, admin, post, comment, body, request)


@router.get("/reports")
def list_reports(
    state: str = Query("open", pattern="^(open|closed)$"),
    admin: Profile = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reports grouped by the reported post or comment, for the admin's own school."""
    statuses = ("open",) if state == "open" else ("actioned", "dismissed")
    reports = list(db.scalars(
        select(ContentReport).where(ContentReport.school_id == admin.school_id, ContentReport.status.in_(statuses))
        .order_by(ContentReport.created_at.desc()).limit(500)
    ))
    groups: dict[tuple[str, str], dict] = {}
    names = {p.id: p.full_name for p in db.scalars(select(Profile).where(Profile.id.in_({r.reporter_id for r in reports})))} if reports else {}
    for r in reports:
        key = ("comment", r.comment_id) if r.comment_id else ("post", r.post_id)
        if key not in groups:
            comment = db.get(Comment, r.comment_id) if r.comment_id else None
            post = db.get(Post, comment.post_id if comment else r.post_id)
            item = comment or post
            author = db.get(Profile, item.author_id)
            groups[key] = {
                "target_type": key[0], "target_id": key[1], "post_id": post.id, "space": post.space,
                "post_title": post.title, "body": item.body, "author": _author(author) if author else None,
                "status": item.status, "moderation_reason": item.moderation_reason, "created_at": item.created_at,
                "reports": [],
            }
        groups[key]["reports"].append({
            "id": r.id, "reason": r.reason, "reason_label": REPORT_REASONS.get(r.reason, r.reason), "details": r.details,
            "reporter": names.get(r.reporter_id), "status": r.status, "created_at": r.created_at,
        })
    return list(groups.values())
