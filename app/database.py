import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "/app/data/dinner.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"
BACKUP_DIR = Path(DB_PATH).parent / "backups"
MAX_BACKUPS = 5

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


def backup_db(reason: str = "manual") -> Path | None:
    """Create a timestamped backup of the SQLite database.

    Uses SQLite's built-in backup API for a safe, consistent copy.
    Keeps only the last MAX_BACKUPS files per reason prefix.
    Returns the backup path, or None if the source database doesn't exist.
    """
    src = Path(DB_PATH)
    if not src.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    dest = BACKUP_DIR / f"dinner_{reason}_{ts}.db"

    # Use SQLite backup API for consistency (no partial writes)
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    logger.info("Database backup created | %s (%s)", dest.name, reason)

    # Prune old backups with the same reason prefix
    pattern = f"dinner_{reason}_*.db"
    backups = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.name)
    for old in backups[:-MAX_BACKUPS]:
        old.unlink()
        logger.info("Pruned old backup | %s", old.name)

    return dest


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


def _table_has_check_constraints(conn, table_name):
    """Return True if the table's CREATE TABLE SQL contains CHECK constraints."""
    row = conn.execute(
        text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table_name},
    ).fetchone()
    return row is not None and "CHECK" in (row[0] or "")


def _rebuild_table_with_constraints(conn, table_name, create_sql):
    """Rebuild a SQLite table to add CHECK constraints (12-step rebuild pattern).

    1. Fix any existing negative values
    2. Rename old table to _old
    3. Create new table with constraints
    4. Copy data from _old to new
    5. Drop _old
    """
    tmp_name = f"{table_name}_old"
    conn.execute(text(f"ALTER TABLE {table_name} RENAME TO {tmp_name}"))
    conn.execute(text(create_sql))
    # Get column names from the new table to build the INSERT
    # Quote all column names to handle reserved words like "group"
    cols = [
        row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})"))
    ]
    col_list = ", ".join(f'"{c}"' for c in cols)
    conn.execute(text(f"INSERT INTO {table_name} ({col_list}) SELECT {col_list} FROM {tmp_name}"))
    conn.execute(text(f"DROP TABLE {tmp_name}"))
    conn.commit()
    logger.info("Rebuilt table %s with CHECK constraints", table_name)


def _add_check_constraints():
    """Add CHECK constraints to existing tables via table rebuild.

    SQLite does not support ALTER TABLE ADD CONSTRAINT, so we must
    recreate the table. This is safe because we copy all data and
    fix any invalid values before rebuilding.
    """
    with engine.connect() as conn:
        # --- meals table ---
        if not _table_has_check_constraints(conn, "meals"):
            # Fix any negative values before rebuilding
            conn.execute(text(
                "UPDATE meals SET frozen_quantity = 0 WHERE frozen_quantity < 0"
            ))
            conn.execute(text(
                "UPDATE meals SET protein_servings = 0 WHERE protein_servings < 0"
            ))
            conn.commit()

            _rebuild_table_with_constraints(conn, "meals", """
                CREATE TABLE meals (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    meal_type VARCHAR(11) DEFAULT 'home_cooked',
                    notes TEXT DEFAULT '',
                    recipe_url TEXT DEFAULT '',
                    has_leftovers INTEGER DEFAULT 0,
                    easy_to_make INTEGER DEFAULT 0,
                    shared_ingredients TEXT DEFAULT '',
                    protein TEXT DEFAULT '',
                    cuisine TEXT DEFAULT '',
                    frozen_quantity INTEGER DEFAULT 0,
                    protein_servings INTEGER DEFAULT 1,
                    active INTEGER DEFAULT 1,
                    created_at DATETIME,
                    CONSTRAINT ck_meals_frozen_quantity_nonneg CHECK (frozen_quantity >= 0),
                    CONSTRAINT ck_meals_protein_servings_nonneg CHECK (protein_servings >= 0)
                )
            """)

        # --- protein_inventory table ---
        if not _table_has_check_constraints(conn, "protein_inventory"):
            # Fix any negative values before rebuilding
            conn.execute(text(
                "UPDATE protein_inventory SET quantity = 0 WHERE quantity < 0"
            ))
            conn.commit()

            _rebuild_table_with_constraints(conn, "protein_inventory", """
                CREATE TABLE protein_inventory (
                    id INTEGER PRIMARY KEY,
                    protein_name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    emoji TEXT DEFAULT '',
                    "group" TEXT DEFAULT 'meat',
                    quantity FLOAT DEFAULT 0,
                    unit TEXT DEFAULT 'servings',
                    CONSTRAINT ck_protein_inventory_quantity_nonneg CHECK (quantity >= 0)
                )
            """)


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
    # Back up before any schema changes
    backup_db(reason="pre_migration")
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    _add_check_constraints()
    _seed_proteins()
