"""Phase 4: one scored answer per student, question set and question.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("question_attempts") as batch:
        batch.create_unique_constraint("uq_attempts_set_question", ["student_id", "set_id", "question_id"])


def downgrade() -> None:
    with op.batch_alter_table("question_attempts") as batch:
        batch.drop_constraint("uq_attempts_set_question", type_="unique")
