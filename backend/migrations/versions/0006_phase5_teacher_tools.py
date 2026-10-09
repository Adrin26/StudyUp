"""Phase 5: assignment windows and feedback release, exam publications and attempts.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ID = sa.Uuid(as_uuid=False)


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("available_from", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("feedback_release", sa.String(20), server_default="immediate", nullable=False))

    op.create_table(
        "exam_publications",
        sa.Column("id", ID, primary_key=True),
        sa.Column("exam_id", ID, sa.ForeignKey("question_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("class_id", ID, sa.ForeignKey("classes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("release_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("published_by", ID, sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("exam_id", "class_id", name="uq_exam_publications_exam_class"),
    )
    op.create_index("ix_exam_publications_exam_id", "exam_publications", ["exam_id"])
    op.create_index("ix_exam_publications_class_id", "exam_publications", ["class_id"])
    op.create_table(
        "exam_attempts",
        sa.Column("id", ID, primary_key=True),
        sa.Column("publication_id", ID, sa.ForeignKey("exam_publications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", ID, sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("marks_awarded", sa.Integer(), nullable=True),
        sa.Column("total_marks", sa.Integer(), nullable=True),
        sa.UniqueConstraint("publication_id", "student_id", name="uq_exam_attempts_student"),
    )
    op.create_index("ix_exam_attempts_publication_id", "exam_attempts", ["publication_id"])
    op.create_index("ix_exam_attempts_student_id", "exam_attempts", ["student_id"])
    op.create_table(
        "exam_answers",
        sa.Column("id", ID, primary_key=True),
        sa.Column("attempt_id", ID, sa.ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", ID, sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("marks_awarded", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_exam_answers_question"),
    )
    op.create_index("ix_exam_answers_attempt_id", "exam_answers", ["attempt_id"])


def downgrade() -> None:
    op.drop_index("ix_exam_answers_attempt_id", "exam_answers")
    op.drop_table("exam_answers")
    op.drop_index("ix_exam_attempts_student_id", "exam_attempts")
    op.drop_index("ix_exam_attempts_publication_id", "exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_index("ix_exam_publications_class_id", "exam_publications")
    op.drop_index("ix_exam_publications_exam_id", "exam_publications")
    op.drop_table("exam_publications")
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("feedback_release")
        batch.drop_column("available_from")
