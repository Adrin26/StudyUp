from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Comment, Post, PostVote, Profile, utcnow
from ..schemas import CommentIn, PostIn, VoteIn
from ..security import get_current_user
from ..services.question_bank import names_lookup

router = APIRouter(prefix="/api/community", tags=["community"])

TEACHER_CATEGORIES = ["Difficult questions", "Teaching strategies", "Exam preparation", "Lesson ideas", "Student misconceptions", "Question quality"]


def _can_read(user: Profile, space: str, school_id: str | None) -> bool:
    if space == "teacher":
        return user.role in ("teacher", "admin")
    # Student space is scoped to one school; teachers there can read (moderate) but not post.
    return user.school_id is not None and user.school_id == school_id


def _can_write(user: Profile, space: str) -> bool:
    return (space == "student" and user.role == "student") or (space == "teacher" and user.role in ("teacher", "admin"))


def _get_post(db: Session, post_id: str, user: Profile) -> Post:
    post = db.get(Post, post_id)
    if post is None or not _can_read(user, post.space, post.school_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
    return post


def _post_payload(post: Post, author: Profile, my_vote: int, topics: dict, subjects: dict) -> dict:
    return {
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
        "author": {"id": author.id, "name": author.full_name, "role": author.role},
        "my_vote": my_vote,
    }


@router.get("/meta")
def meta(user: Profile = Depends(get_current_user)):
    return {"teacher_categories": TEACHER_CATEGORIES, "can_post_student": user.role == "student", "can_post_teacher": user.role in ("teacher", "admin")}


@router.get("/posts")
def list_posts(
    space: str = Query("student", pattern="^(student|teacher)$"),
    subject_id: str | None = None,
    topic_id: str | None = None,
    category: str | None = None,
    q: str | None = Query(None, max_length=100),
    sort: str = Query("new", pattern="^(new|top)$"),
    page: int = Query(1, ge=1),
    user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _can_read(user, space, user.school_id if space == "student" else None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot access this community")
    stmt = select(Post, Profile).join(Profile, Profile.id == Post.author_id).where(Post.space == space)
    if space == "student":
        stmt = stmt.where(Post.school_id == user.school_id)
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
    votes = dict(db.execute(select(PostVote.post_id, PostVote.value).where(PostVote.user_id == user.id, PostVote.post_id.in_([p.id for p, _ in rows]))).all()) if rows else {}
    topics, subjects = names_lookup(db)
    return [_post_payload(p, a, votes.get(p.id, 0), topics, subjects) for p, a in rows]


@router.post("/posts")
def create_post(body: PostIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    if not _can_write(user, body.space):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot post in this community")
    post = Post(
        author_id=user.id,
        space=body.space,
        school_id=user.school_id if body.space == "student" else None,
        subject_id=body.subject_id,
        topic_id=body.topic_id,
        category=body.category if body.space == "teacher" else None,
        title=body.title.strip(),
        body=body.body.strip(),
    )
    db.add(post)
    db.commit()
    topics, subjects = names_lookup(db)
    return _post_payload(post, user, 0, topics, subjects)


@router.get("/posts/{post_id}")
def get_post(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    author = db.get(Profile, post.author_id)
    vote = db.get(PostVote, {"post_id": post.id, "user_id": user.id})
    comments = db.execute(
        select(Comment, Profile).join(Profile, Profile.id == Comment.author_id).where(Comment.post_id == post.id).order_by(Comment.created_at)
    ).all()
    topics, subjects = names_lookup(db)
    return {
        **_post_payload(post, author, vote.value if vote else 0, topics, subjects),
        "can_comment": _can_write(user, post.space),
        "comments": [
            {"id": c.id, "body": c.body, "created_at": c.created_at, "author": {"id": a.id, "name": a.full_name, "role": a.role}} for c, a in comments
        ],
    }


@router.post("/posts/{post_id}/comments")
def add_comment(post_id: str, body: CommentIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if not _can_write(user, post.space):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot comment in this community")
    comment = Comment(post_id=post.id, author_id=user.id, body=body.body.strip(), created_at=utcnow())
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    db.commit()
    return {"id": comment.id, "body": comment.body, "created_at": comment.created_at, "author": {"id": user.id, "name": user.full_name, "role": user.role}}


@router.post("/posts/{post_id}/vote")
def vote(post_id: str, body: VoteIn, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
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


@router.delete("/posts/{post_id}", status_code=204)
def delete_post(post_id: str, user: Profile = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _get_post(db, post_id, user)
    if post.author_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only delete your own posts")
    db.delete(post)
    db.commit()
