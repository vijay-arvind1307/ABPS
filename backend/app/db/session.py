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
