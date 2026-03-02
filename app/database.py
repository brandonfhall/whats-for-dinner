import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = f"sqlite:///{os.getenv('DB_PATH', '/app/data/dinner.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_migrations():
    """Add new columns to existing tables without dropping data."""
    with engine.connect() as conn:
        meal_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(meals)"))}
        if "protein" not in meal_cols:
            conn.execute(text("ALTER TABLE meals ADD COLUMN protein TEXT DEFAULT ''"))
            conn.commit()

        day_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(plan_days)"))}
        if "carry_forward" not in day_cols:
            conn.execute(text("ALTER TABLE plan_days ADD COLUMN carry_forward INTEGER DEFAULT 0"))
            conn.commit()

        if "cuisine" not in meal_cols:
            conn.execute(text("ALTER TABLE meals ADD COLUMN cuisine TEXT DEFAULT ''"))
            conn.commit()

        plan_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(weekly_plans)"))}
        if "notes" not in plan_cols:
            conn.execute(text("ALTER TABLE weekly_plans ADD COLUMN notes TEXT DEFAULT ''"))
            conn.commit()


def init_db():
    from app import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _run_migrations()
