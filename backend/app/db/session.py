import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Handle SQLite connect args for multi-threading and canonicalize path
connect_args = {}
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///./") or db_url == "sqlite:///abps.db":
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_file = os.path.join(backend_dir, "abps.db").replace("\\", "/")
    db_url = f"sqlite:///{db_file}"

if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_schema():
    from app.db.base import Base
    import app.models.models  # Register models
    Base.metadata.create_all(bind=engine)
    if str(engine.url).startswith("sqlite"):
        with engine.connect() as conn:
            try:
                res = conn.exec_driver_sql("PRAGMA table_info(train_section_occupancies)").fetchall()
                cols = [r[1] for r in res]
                new_cols = {
                    "journey_date": "DATETIME",
                    "entry_time": "DATETIME",
                    "exit_time": "DATETIME",
                    "is_live": "BOOLEAN DEFAULT 0",
                    "last_updated": "DATETIME"
                }
                for col_name, col_type in new_cols.items():
                    if col_name not in cols:
                        conn.exec_driver_sql(f"ALTER TABLE train_section_occupancies ADD COLUMN {col_name} {col_type}")
                        conn.commit()
            except Exception as ex:
                print(f"[SCHEMA_INIT] Notice: {ex}")


init_schema()

