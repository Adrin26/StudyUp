"""Phase 6: community moderation, replies, bookmarks and reports; XP ledger; school calendar.

Revision ID: 0007
Revises: 0006
"""

import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.Uuid(as_uuid=False)


def _moderation_columns(batch, table: str) -> None:
    batch.add_column(sa.Column("status", sa.String(20), server_default="visible", nullable=False))
    batch.add_column(sa.Column("moderation_reason", sa.String(300), nullable=True))
    batch.add_column(sa.Column("moderated_by", ID, nullable=True))
    batch.add_column(sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True))
    batch.create_foreign_key(f"fk_{table}_moderated_by", "profiles", ["moderated_by"], ["id"])
    batch.create_check_constraint(f"ck_{table}_status", "status IN ('visible', 'hidden')")


def upgrade() -> None:
    with op.batch_alter_table("posts") as batch:
        _moderation_columns(batch, "posts")
    with op.batch_alter_table("comments") as batch:
        _moderation_columns(batch, "comments")
        batch.add_column(sa.Column("parent_id", ID, nullable=True))
        batch.create_foreign_key("fk_comments_parent_id", "comments", ["parent_id"], ["id"], ondelete="CASCADE")

    op.create_table(
        "post_bookmarks",
        sa.Column("post_id", ID, sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "content_reports",
        sa.Column("id", ID, primary_key=True),
        sa.Column("school_id", ID, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", ID, sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("comment_id", ID, sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("details", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="open", nullable=False),
        sa.Column("resolved_by", ID, sa.ForeignKey("profiles.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('open', 'actioned', 'dismissed')", name="ck_content_reports_status"),
        sa.CheckConstraint("(post_id IS NULL) <> (comment_id IS NULL)", name="ck_content_reports_target"),
    )
    for col in ("school_id", "reporter_id", "post_id", "comment_id"):
        op.create_index(f"ix_content_reports_{col}", "content_reports", [col])

    op.create_table(
        "student_xp_events",
        sa.Column("id", ID, primary_key=True),
        sa.Column("student_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("ref_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_student_xp_events_student_id", "student_xp_events", ["student_id"])
    op.create_index("ix_student_xp_events_created_at", "student_xp_events", ["created_at"])

    # XP earned before the ledger existed becomes one opening-balance entry, so totals still add up.
    conn = op.get_bind()
    events = sa.table("student_xp_events", sa.column("id", ID), sa.column("student_id", ID), sa.column("amount", sa.Integer),
                      sa.column("reason", sa.String), sa.column("created_at", sa.DateTime(timezone=True)))
    now = datetime.now(timezone.utc)
    rows = conn.execute(sa.text("SELECT id, xp FROM profiles WHERE role = 'student' AND xp > 0")).all()
    if rows:
        op.bulk_insert(events, [{"id": str(uuid.uuid4()), "student_id": str(r[0]), "amount": r[1], "reason": "opening_balance", "created_at": now} for r in rows])

    op.create_table(
        "calendar_events",
        sa.Column("id", ID, primary_key=True),
        sa.Column("school_id", ID, sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_by", ID, sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_calendar_events_dates"),
        sa.CheckConstraint("audience IN ('all', 'teachers', 'students')", name="ck_calendar_events_audience"),
    )
    op.create_index("ix_calendar_events_school_id", "calendar_events", ["school_id"])
    op.create_index("ix_calendar_events_start_date", "calendar_events", ["start_date"])


def downgrade() -> None:
    op.drop_index("ix_calendar_events_start_date", "calendar_events")
    op.drop_index("ix_calendar_events_school_id", "calendar_events")
    op.drop_table("calendar_events")
    op.drop_index("ix_student_xp_events_created_at", "student_xp_events")
    op.drop_index("ix_student_xp_events_student_id", "student_xp_events")
    op.drop_table("student_xp_events")
    for col in ("comment_id", "post_id", "reporter_id", "school_id"):
        op.drop_index(f"ix_content_reports_{col}", "content_reports")
    op.drop_table("content_reports")
    op.drop_table("post_bookmarks")
    with op.batch_alter_table("comments") as batch:
        batch.drop_constraint("fk_comments_parent_id", type_="foreignkey")
        batch.drop_column("parent_id")
        batch.drop_constraint("ck_comments_status", type_="check")
        batch.drop_constraint("fk_comments_moderated_by", type_="foreignkey")
        for col in ("moderated_at", "moderated_by", "moderation_reason", "status"):
            batch.drop_column(col)
    with op.batch_alter_table("posts") as batch:
        batch.drop_constraint("ck_posts_status", type_="check")
        batch.drop_constraint("fk_posts_moderated_by", type_="foreignkey")
        for col in ("moderated_at", "moderated_by", "moderation_reason", "status"):
            batch.drop_column(col)
