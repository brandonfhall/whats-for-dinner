"""Tests for database migration logic (CHECK constraints on existing tables)."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base, _run_migrations, _add_check_constraints


def _create_legacy_db(db_path):
    """Create a database with the old schema (no CHECK constraints)."""
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as conn:
        conn.execute(text("""
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
                created_at DATETIME
            )
        """))
        conn.execute(text("""
            CREATE TABLE protein_inventory (
                id INTEGER PRIMARY KEY,
                protein_name TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                emoji TEXT DEFAULT '',
                "group" TEXT DEFAULT 'meat',
                quantity FLOAT DEFAULT 0,
                unit TEXT DEFAULT 'servings'
            )
        """))
        conn.commit()
    return engine


def test_migration_adds_check_constraints_to_meals(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = _create_legacy_db(db_path)

    with engine.connect() as conn:
        # Insert a meal with a negative frozen_quantity (should be allowed pre-migration)
        conn.execute(text(
            "INSERT INTO meals (name, frozen_quantity, protein_servings) VALUES ('Bad Meal', -5, -2)"
        ))
        conn.commit()

    # Run migration
    from app.database import _table_has_check_constraints
    with engine.connect() as conn:
        assert not _table_has_check_constraints(conn, "meals")

    # Temporarily swap the module-level engine
    import app.database as db_mod
    original_engine = db_mod.engine
    db_mod.engine = engine
    try:
        _add_check_constraints()
    finally:
        db_mod.engine = original_engine

    # Verify constraints exist
    with engine.connect() as conn:
        assert _table_has_check_constraints(conn, "meals")

        # Verify negative values were fixed
        row = conn.execute(text("SELECT frozen_quantity, protein_servings FROM meals WHERE name='Bad Meal'")).fetchone()
        assert row[0] == 0
        assert row[1] == 0

        # Verify CHECK constraint actually blocks negative inserts
        try:
            conn.execute(text(
                "INSERT INTO meals (name, frozen_quantity) VALUES ('Fail', -1)"
            ))
            conn.commit()
            assert False, "CHECK constraint should have rejected negative frozen_quantity"
        except Exception:
            conn.rollback()


def test_migration_adds_check_constraints_to_protein_inventory(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = _create_legacy_db(db_path)

    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO protein_inventory (protein_name, display_name, quantity) VALUES ('Chicken', 'Chicken', -3)"
        ))
        conn.commit()

    import app.database as db_mod
    original_engine = db_mod.engine
    db_mod.engine = engine
    try:
        _add_check_constraints()
    finally:
        db_mod.engine = original_engine

    with engine.connect() as conn:
        from app.database import _table_has_check_constraints
        assert _table_has_check_constraints(conn, "protein_inventory")

        # Verify negative value was fixed
        row = conn.execute(text("SELECT quantity FROM protein_inventory WHERE protein_name='Chicken'")).fetchone()
        assert row[0] == 0

        # Verify CHECK constraint blocks negative inserts
        try:
            conn.execute(text(
                "INSERT INTO protein_inventory (protein_name, display_name, quantity) VALUES ('Bad', 'Bad', -1)"
            ))
            conn.commit()
            assert False, "CHECK constraint should have rejected negative quantity"
        except Exception:
            conn.rollback()


def test_migration_preserves_existing_data(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = _create_legacy_db(db_path)

    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO meals (name, meal_type, frozen_quantity, protein_servings, protein) "
            "VALUES ('Good Meal', 'home_cooked', 5, 2, 'Chicken')"
        ))
        conn.execute(text(
            "INSERT INTO protein_inventory (protein_name, display_name, emoji, quantity) "
            "VALUES ('Beef', 'Beef', '🥩', 10)"
        ))
        conn.commit()

    import app.database as db_mod
    original_engine = db_mod.engine
    db_mod.engine = engine
    try:
        _add_check_constraints()
    finally:
        db_mod.engine = original_engine

    with engine.connect() as conn:
        meal = conn.execute(text("SELECT name, frozen_quantity, protein_servings, protein FROM meals")).fetchone()
        assert meal[0] == "Good Meal"
        assert meal[1] == 5
        assert meal[2] == 2
        assert meal[3] == "Chicken"

        protein = conn.execute(text("SELECT protein_name, display_name, emoji, quantity FROM protein_inventory")).fetchone()
        assert protein[0] == "Beef"
        assert protein[1] == "Beef"
        assert protein[2] == "🥩"
        assert protein[3] == 10


def test_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = _create_legacy_db(db_path)

    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO meals (name, frozen_quantity) VALUES ('Test', 3)"
        ))
        conn.commit()

    import app.database as db_mod
    original_engine = db_mod.engine
    db_mod.engine = engine
    try:
        # Run migration twice
        _add_check_constraints()
        _add_check_constraints()
    finally:
        db_mod.engine = original_engine

    with engine.connect() as conn:
        row = conn.execute(text("SELECT name, frozen_quantity FROM meals")).fetchone()
        assert row[0] == "Test"
        assert row[1] == 3
