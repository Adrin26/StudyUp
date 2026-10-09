import logging
from collections.abc import Iterator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


log = logging.getLogger("minda.db")


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    eng = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        # Let SQLAlchemy own transactions so SAVEPOINTs (begin_nested) work with pysqlite.
        @event.listens_for(eng, "connect")
        def _on_connect(dbapi_conn, _):
            dbapi_conn.isolation_level = None
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(eng, "begin")
        def _on_begin(conn):
            conn.exec_driver_sql("BEGIN")

    return eng


engine = _make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """SQLite (tests, quick demos) is created from the models; PostgreSQL only via Alembic."""
    from . import models  # noqa: F401  (register models)

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(bind=engine)
        return
    with engine.connect() as conn:
        if not inspect(conn).has_table("alembic_version"):
            log.warning("Database has no migrations applied. Run `alembic upgrade head` in backend/.")
