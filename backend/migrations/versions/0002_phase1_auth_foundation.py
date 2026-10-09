"""Phase 1 auth foundation: account status, usernames, local credentials, reset tokens, audit log.

Also drops profiles.teacher_types: class/subject-teacher responsibilities are
now derived from classes.class_teacher_id and teacher_subjects.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09 10:28:01.631259
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("school_id", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.create_index(batch_op.f("ix_audit_logs_action"), ["action"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_logs_actor_id"), ["actor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_logs_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_audit_logs_school_id"), ["school_id"], unique=False)

    op.create_table(
        "local_credentials",
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id"),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("profile_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_by", sa.Uuid(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["profiles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    with op.batch_alter_table("password_reset_tokens") as batch_op:
        batch_op.create_index(batch_op.f("ix_password_reset_tokens_profile_id"), ["profile_id"], unique=False)

    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch_op.add_column(sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f("ix_profiles_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_profiles_username"), ["username"], unique=True)
        batch_op.create_check_constraint("ck_profiles_role", "role IN ('admin', 'teacher', 'student')")
        batch_op.create_check_constraint("ck_profiles_status", "status IN ('active', 'disabled')")
        batch_op.drop_column("teacher_types")


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(sa.Column("teacher_types", sa.JSON(), server_default=sa.text("'[]'"), nullable=False))
        batch_op.drop_constraint("ck_profiles_status", type_="check")
        batch_op.drop_constraint("ck_profiles_role", type_="check")
        batch_op.drop_index(batch_op.f("ix_profiles_username"))
        batch_op.drop_index(batch_op.f("ix_profiles_status"))
        batch_op.drop_column("updated_at")
        batch_op.drop_column("last_login_at")
        batch_op.drop_column("status")
        batch_op.drop_column("username")

    with op.batch_alter_table("password_reset_tokens") as batch_op:
        batch_op.drop_index(batch_op.f("ix_password_reset_tokens_profile_id"))
    op.drop_table("password_reset_tokens")
    op.drop_table("local_credentials")
    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_logs_school_id"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_created_at"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_actor_id"))
        batch_op.drop_index(batch_op.f("ix_audit_logs_action"))
    op.drop_table("audit_logs")
