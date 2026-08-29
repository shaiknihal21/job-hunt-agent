from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_sqlite_columns():
    """Add new resume columns to existing SQLite databases."""
    if not settings.database_url.startswith("sqlite"):
        return

    import sqlalchemy

    new_columns = {
        "master_resume_id": "INTEGER",
        "target_role": "VARCHAR(200)",
        "ats_score_before": "FLOAT",
        "ats_score_after": "FLOAT",
        "ats_breakdown": "JSON",
        "gap_report": "JSON",
        "keywords_emphasized": "JSON",
        "changes_summary": "JSON",
        "validation_status": "VARCHAR(50)",
        "validation_errors": "JSON",
    }

    with engine.connect() as conn:
        existing = {
            row[1]
            for row in conn.execute(sqlalchemy.text("PRAGMA table_info(resumes)")).fetchall()
        }
        for column, col_type in new_columns.items():
            if column not in existing:
                conn.execute(sqlalchemy.text(f"ALTER TABLE resumes ADD COLUMN {column} {col_type}"))
        conn.commit()


def init_db():
    from app.models import profile  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite_columns()
