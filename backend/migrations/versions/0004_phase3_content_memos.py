"""Phase 3 content management and school memos.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subjects") as batch:
        batch.add_column(sa.Column("status", sa.String(20), server_default="published", nullable=False))
        batch.create_check_constraint("ck_subjects_status", "status IN ('draft', 'published', 'archived')")
    op.create_table(
        "subject_form_levels",
        sa.Column("subject_id", sa.Uuid(as_uuid=False), sa.ForeignKey("subjects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("form", sa.Integer(), primary_key=True),
    )
    with op.batch_alter_table("topics") as batch:
        batch.add_column(sa.Column("parent_id", sa.Uuid(as_uuid=False), nullable=True))
        batch.add_column(sa.Column("status", sa.String(20), server_default="published", nullable=False))
        batch.create_foreign_key("fk_topics_parent_id", "topics", ["parent_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_topics_parent_id", ["parent_id"])
        batch.create_check_constraint("ck_topics_status", "status IN ('draft', 'published', 'archived')")
    op.create_table(
        "learning_objectives",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("topic_id", sa.Uuid(as_uuid=False), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_index("ix_learning_objectives_topic_id", "learning_objectives", ["topic_id"])
    op.create_table(
        "topic_prerequisites",
        sa.Column("topic_id", sa.Uuid(as_uuid=False), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("prerequisite_id", sa.Uuid(as_uuid=False), sa.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
    )
    with op.batch_alter_table("lessons") as batch:
        batch.add_column(sa.Column("status", sa.String(20), server_default="published", nullable=False))
        batch.create_check_constraint("ck_lessons_status", "status IN ('draft', 'published', 'archived')")
    op.add_column("questions", sa.Column("form", sa.Integer(), nullable=True))
    op.add_column("questions", sa.Column("attribution", sa.String(300), nullable=True))
    op.execute("UPDATE questions SET status = 'draft' WHERE status = 'pending_review'")
    op.execute("UPDATE questions SET status = 'archived' WHERE status = 'rejected'")
    with op.batch_alter_table("questions") as batch:
        batch.create_check_constraint("ck_questions_status", "status IN ('draft', 'published', 'archived')")

    op.create_table(
        "school_memos",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("school_id", sa.Uuid(as_uuid=False), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("audience", sa.String(20), server_default="all", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("publish_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("requires_acknowledgement", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=False), sa.ForeignKey("profiles.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_memos_status"),
        sa.CheckConstraint("audience IN ('all', 'teachers', 'students')", name="ck_memos_audience"),
    )
    op.create_index("ix_school_memos_school_id", "school_memos", ["school_id"])
    op.create_table(
        "memo_attachments",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("memo_id", sa.Uuid(as_uuid=False), sa.ForeignKey("school_memos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(300), nullable=False),
    )
    op.create_index("ix_memo_attachments_memo_id", "memo_attachments", ["memo_id"])
    op.create_table(
        "memo_reads",
        sa.Column("memo_id", sa.Uuid(as_uuid=False), sa.ForeignKey("school_memos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "memo_acknowledgements",
        sa.Column("memo_id", sa.Uuid(as_uuid=False), sa.ForeignKey("school_memos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("memo_acknowledgements")
    op.drop_table("memo_reads")
    op.drop_index("ix_memo_attachments_memo_id", "memo_attachments")
    op.drop_table("memo_attachments")
    op.drop_index("ix_school_memos_school_id", "school_memos")
    op.drop_table("school_memos")
    with op.batch_alter_table("questions") as batch:
        batch.drop_constraint("ck_questions_status", type_="check")
    op.drop_column("questions", "attribution")
    op.drop_column("questions", "form")
    with op.batch_alter_table("lessons") as batch:
        batch.drop_constraint("ck_lessons_status", type_="check")
        batch.drop_column("status")
    op.drop_table("topic_prerequisites")
    op.drop_index("ix_learning_objectives_topic_id", "learning_objectives")
    op.drop_table("learning_objectives")
    with op.batch_alter_table("topics") as batch:
        batch.drop_constraint("ck_topics_status", type_="check")
        batch.drop_index("ix_topics_parent_id")
        batch.drop_constraint("fk_topics_parent_id", type_="foreignkey")
        batch.drop_column("status")
        batch.drop_column("parent_id")
    op.drop_table("subject_form_levels")
    with op.batch_alter_table("subjects") as batch:
        batch.drop_constraint("ck_subjects_status", type_="check")
        batch.drop_column("status")
