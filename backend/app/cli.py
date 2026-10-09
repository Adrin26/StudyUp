"""Protected administrative commands. Run from backend/ with server access.

    python -m app.cli create-admin --email admin@school.edu.my --name "Puan Admin" [--username admin] [--school-id ID]
    python -m app.cli grant-admin --email someone@school.edu.my      (Supabase: promote an existing profile)

There is deliberately no HTTP endpoint that can create an admin account.
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import func, select

from .config import get_settings
from .database import SessionLocal
from .models import Profile, School
from .services import audit, passwords


def _fail(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def _read_password(identifiers: tuple[str | None, ...]) -> str:
    password = os.environ.get("MINDA_ADMIN_PASSWORD")
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            _fail("passwords do not match")
    if problems := passwords.password_problems(password, identifiers):
        _fail(" ".join(problems))
    return password


def _school(db, school_id: str | None, school_name: str | None) -> School:
    if school_id:
        school = db.get(School, school_id)
        if school is None:
            _fail(f"school {school_id} not found")
        return school
    schools = list(db.scalars(select(School)))
    if len(schools) == 1:
        return schools[0]
    if not schools:
        if not school_name:
            _fail("no school exists yet; pass --school-name to create one")
        school = School(name=school_name)
        db.add(school)
        db.flush()
        return school
    _fail("several schools exist; pass --school-id:\n" + "\n".join(f"  {s.id}  {s.name}" for s in schools))


def create_admin(args) -> None:
    if get_settings().auth_mode != "local":
        _fail("create-admin is for AUTH_MODE=local. On Supabase, create the user in Supabase Auth, then run grant-admin.")
    email = args.email.strip().lower()
    username = args.username.strip().lower() if args.username else None
    with SessionLocal() as db:
        if db.scalar(select(Profile).where(func.lower(Profile.email) == email)):
            _fail(f"an account with email {email} already exists")
        if username and db.scalar(select(Profile).where(func.lower(Profile.username) == username)):
            _fail(f"username {username} is taken")
        password = _read_password((email, username))
        school = _school(db, args.school_id, args.school_name)
        admin = Profile(email=email, username=username, full_name=args.name.strip(), role="admin", school_id=school.id)
        db.add(admin)
        db.flush()
        passwords.set_password(db, admin, password)
        audit.record(db, "user.create", "profile", admin.id, school_id=school.id, details={"role": "admin", "via": "cli"})
        db.commit()
        print(f"Created admin {email} for {school.name}")


def grant_admin(args) -> None:
    email = args.email.strip().lower()
    with SessionLocal() as db:
        profile = db.scalar(select(Profile).where(func.lower(Profile.email) == email))
        if profile is None:
            _fail(f"no profile with email {email}")
        previous = profile.role
        profile.role = "admin"
        audit.record(db, "user.role_change", "profile", profile.id, school_id=profile.school_id, details={"from": previous, "to": "admin", "via": "cli"})
        db.commit()
        print(f"{email} is now an admin")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="MINDA administrative commands")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create-admin", help="create an admin account (AUTH_MODE=local)")
    p.add_argument("--email", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--username")
    p.add_argument("--school-id")
    p.add_argument("--school-name", help="create the school if none exists yet")
    p.set_defaults(func=create_admin)

    g = sub.add_parser("grant-admin", help="promote an existing profile to admin")
    g.add_argument("--email", required=True)
    g.set_defaults(func=grant_admin)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
