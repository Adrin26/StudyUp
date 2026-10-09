"""Phase 2 school administration.

- School profile fields (address, contact, logo URL, timezone, description).
- Academic years and terms; classes belong to an academic year (replaces classes.year)
  and can be archived. Existing classes get an academic year per (school, year).
- Enrolment history: class_students rows carry status/enrolled_at/left_at and are
  closed instead of deleted when a student transfers or leaves.
- Student and staff ID numbers (unique per school) and teacher department.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-09 11:00:00
"""

import uuid
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("schools") as batch_op:
        batch_op.add_column(sa.Column("address", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("logo_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("timezone", sa.String(length=60), server_default="Asia/Kuala_Lumpur", nullable=False))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "academic_years",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("school_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_academic_years_dates"),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_id", "name", name="uq_academic_years_school_name"),
    )
    with op.batch_alter_table("academic_years") as batch_op:
        batch_op.create_index(batch_op.f("ix_academic_years_school_id"), ["school_id"], unique=False)

    op.create_table(
        "academic_terms",
        sa.Column("id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("academic_year_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.CheckConstraint("end_date > start_date", name="ck_academic_terms_dates"),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("academic_year_id", "name", name="uq_academic_terms_year_name"),
    )
    with op.batch_alter_table("academic_terms") as batch_op:
        batch_op.create_index(batch_op.f("ix_academic_terms_academic_year_id"), ["academic_year_id"], unique=False)

    with op.batch_alter_table("classes") as batch_op:
        batch_op.add_column(sa.Column("academic_year_id", sa.Uuid(as_uuid=False), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))

    _backfill_academic_years()

    with op.batch_alter_table("classes") as batch_op:
        batch_op.alter_column("academic_year_id", existing_type=sa.Uuid(as_uuid=False), nullable=False)
        batch_op.create_foreign_key("fk_classes_academic_year_id", "academic_years", ["academic_year_id"], ["id"])
        batch_op.create_index(batch_op.f("ix_classes_academic_year_id"), ["academic_year_id"], unique=False)
        batch_op.create_unique_constraint("uq_classes_year_name", ["academic_year_id", "name"])
        batch_op.create_check_constraint("ck_classes_status", "status IN ('active', 'archived')")
        batch_op.create_check_constraint("ck_classes_form", "form BETWEEN 1 AND 5")
        batch_op.drop_column("year")

    # recreate="always": SQLite cannot ADD COLUMN with a non-constant default.
    with op.batch_alter_table("class_students", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch_op.add_column(sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch_op.add_column(sa.Column("left_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint("ck_class_students_status", "status IN ('active', 'transferred', 'withdrawn')")

    with op.batch_alter_table("profiles") as batch_op:
        batch_op.add_column(sa.Column("student_number", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("staff_number", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("department", sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint("uq_profiles_school_student_number", ["school_id", "student_number"])
        batch_op.create_unique_constraint("uq_profiles_school_staff_number", ["school_id", "staff_number"])


def _backfill_academic_years() -> None:
    """One academic year per (school, calendar year) already used by a class; the latest is current."""
    bind = op.get_bind()
    classes = sa.table("classes", sa.column("id"), sa.column("school_id"), sa.column("year"), sa.column("academic_year_id"))
    years = sa.table(
        "academic_years",
        sa.column("id"), sa.column("school_id"), sa.column("name"), sa.column("start_date", sa.Date()),
        sa.column("end_date", sa.Date()), sa.column("is_current", sa.Boolean()), sa.column("created_at", sa.DateTime(timezone=True)),
    )
    pairs = bind.execute(sa.select(classes.c.school_id, classes.c.year).distinct()).all()
    latest: dict[str, int] = {}
    for school_id, year in pairs:
        latest[school_id] = max(latest.get(school_id, year), year)
    for school_id, year in pairs:
        year_id = str(uuid.uuid4())
        bind.execute(years.insert().values(
            id=year_id, school_id=school_id, name=str(year), start_date=date(year, 1, 1), end_date=date(year, 12, 31),
            is_current=year == latest[school_id], created_at=sa.func.now(),
        ))
        bind.execute(
            classes.update().where(classes.c.school_id == school_id, classes.c.year == year).values(academic_year_id=year_id)
        )


def downgrade() -> None:
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_constraint("uq_profiles_school_staff_number", type_="unique")
        batch_op.drop_constraint("uq_profiles_school_student_number", type_="unique")
        batch_op.drop_column("department")
        batch_op.drop_column("staff_number")
        batch_op.drop_column("student_number")

    # Enrolment history cannot be represented in the old schema; ended enrolments are dropped.
    op.execute("DELETE FROM class_students WHERE status <> 'active'")
    with op.batch_alter_table("class_students") as batch_op:
        batch_op.drop_constraint("ck_class_students_status", type_="check")
        batch_op.drop_column("left_at")
        batch_op.drop_column("enrolled_at")
        batch_op.drop_column("status")

    with op.batch_alter_table("classes") as batch_op:
        batch_op.add_column(sa.Column("year", sa.Integer(), nullable=True))
    bind = op.get_bind()
    classes = sa.table("classes", sa.column("id"), sa.column("academic_year_id"), sa.column("year"))
    years = sa.table("academic_years", sa.column("id"), sa.column("start_date", sa.Date()))
    for year_id, start in bind.execute(sa.select(years.c.id, years.c.start_date)).all():
        bind.execute(classes.update().where(classes.c.academic_year_id == year_id).values(year=start.year))
    with op.batch_alter_table("classes") as batch_op:
        batch_op.alter_column("year", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("ck_classes_form", type_="check")
        batch_op.drop_constraint("ck_classes_status", type_="check")
        batch_op.drop_constraint("uq_classes_year_name", type_="unique")
        batch_op.drop_index(batch_op.f("ix_classes_academic_year_id"))
        batch_op.drop_constraint("fk_classes_academic_year_id", type_="foreignkey")
        batch_op.drop_column("status")
        batch_op.drop_column("academic_year_id")

    with op.batch_alter_table("academic_terms") as batch_op:
        batch_op.drop_index(batch_op.f("ix_academic_terms_academic_year_id"))
    op.drop_table("academic_terms")
    with op.batch_alter_table("academic_years") as batch_op:
        batch_op.drop_index(batch_op.f("ix_academic_years_school_id"))
    op.drop_table("academic_years")

    with op.batch_alter_table("schools") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("description")
        batch_op.drop_column("timezone")
        batch_op.drop_column("logo_url")
        batch_op.drop_column("email")
        batch_op.drop_column("phone")
        batch_op.drop_column("address")
