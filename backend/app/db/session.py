import os
import sqlite3
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from app.core.config import settings

db_url = settings.DATABASE_URL
connect_args = {}
engine_kwargs = {"echo": settings.DB_ECHO}

# Canonicalize SQLite path if local
if db_url.startswith("sqlite:///./") or db_url == "sqlite:///abps.db":
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_file = os.path.join(backend_dir, "abps.db").replace("\\", "/")
    db_url = f"sqlite:///{db_file}"

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    connect_args["timeout"] = 15
    engine_kwargs["connect_args"] = connect_args
elif "postgresql" in db_url:
    engine_kwargs["poolclass"] = QueuePool
    engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
    engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT
    engine_kwargs["pool_recycle"] = settings.DB_POOL_RECYCLE
    engine_kwargs["pool_pre_ping"] = True

engine = create_engine(db_url, **engine_kwargs)

# Configure SQLite WAL mode and pragmas on connect
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=10000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction_scope(db: Session):
    """Transactional scope around a series of operations with rollback on error."""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


def init_schema():
    from app.db.base import Base
    import app.models.models  # Register models
    Base.metadata.create_all(bind=engine)


init_schema()

