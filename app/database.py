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

        if "frozen_quantity" not in meal_cols:
            conn.execute(text("ALTER TABLE meals ADD COLUMN frozen_quantity INTEGER DEFAULT 0"))
            conn.commit()

        if "protein_servings" not in meal_cols:
            conn.execute(text("ALTER TABLE meals ADD COLUMN protein_servings INTEGER DEFAULT 1"))
            conn.commit()


DEFAULT_PROTEINS = [
    {"protein_name": "Chicken",    "display_name": "Chicken",    "emoji": "\U0001f357", "group": "meat"},
    {"protein_name": "Beef",       "display_name": "Beef",       "emoji": "\U0001f969", "group": "meat"},
    {"protein_name": "Pork",       "display_name": "Pork",       "emoji": "\U0001f437", "group": "meat"},
    {"protein_name": "Turkey",     "display_name": "Turkey",     "emoji": "\U0001f983", "group": "meat"},
    {"protein_name": "Fish",       "display_name": "Fish",       "emoji": "\U0001f41f", "group": "meat"},
    {"protein_name": "Seafood",    "display_name": "Seafood",    "emoji": "\U0001f990", "group": "meat"},
    {"protein_name": "Lamb",       "display_name": "Lamb",       "emoji": "\U0001f411", "group": "meat"},
    {"protein_name": "Tofu",       "display_name": "Tofu",       "emoji": "\U0001fad8", "group": "veg"},
    {"protein_name": "Eggs",       "display_name": "Eggs",       "emoji": "\U0001f95a", "group": "veg"},
    {"protein_name": "Beans",      "display_name": "Beans",      "emoji": "\U0001fad8", "group": "veg"},
    {"protein_name": "Lentils",    "display_name": "Lentils",    "emoji": "\U0001f331", "group": "veg"},
    {"protein_name": "Tempeh",     "display_name": "Tempeh",     "emoji": "\U0001f33f", "group": "veg"},
    {"protein_name": "Cheese",     "display_name": "Cheese",     "emoji": "\U0001f9c0", "group": "veg"},
    {"protein_name": "Vegetarian", "display_name": "Vegetarian", "emoji": "\U0001f966", "group": "veg"},
]


def _seed_proteins():
    """Seed the protein_inventory table with defaults if empty."""
    from app.models import ProteinInventory
    db = SessionLocal()
    try:
        if db.query(ProteinInventory).count() == 0:
            for p in DEFAULT_PROTEINS:
                db.add(ProteinInventory(**p))
            db.commit()
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401 — ensures models are registered
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _seed_proteins()
