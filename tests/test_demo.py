"""Tests for demo mode data seeding."""

import os
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import (
    Base,
    DEMO_MEALS,
    DEMO_PROTEIN_QUANTITIES,
    _seed_demo_data,
    _seed_proteins,
)
from app.models import Meal, ProteinInventory


def _make_test_session(tmp_path):
    """Create a test engine/session bound to a temp SQLite file."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'demo_test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_demo_seed_populates_meals_when_enabled(tmp_path):
    """DEMO_MODE=true seeds meals into an empty database."""
    TestSession = _make_test_session(tmp_path)
    with patch("app.database.SessionLocal", TestSession), \
         patch.dict(os.environ, {"DEMO_MODE": "true"}):
        _seed_proteins()
        _seed_demo_data()
    db = TestSession()
    try:
        assert db.query(Meal).count() == len(DEMO_MEALS)
    finally:
        db.close()


def test_demo_seed_does_not_run_when_disabled(tmp_path):
    """DEMO_MODE unset or false should not seed any meals."""
    TestSession = _make_test_session(tmp_path)
    with patch("app.database.SessionLocal", TestSession), \
         patch.dict(os.environ, {}, clear=True):
        _seed_demo_data()
    db = TestSession()
    try:
        assert db.query(Meal).count() == 0
    finally:
        db.close()


def test_demo_seed_does_not_run_when_false(tmp_path):
    """DEMO_MODE=false should not seed any meals."""
    TestSession = _make_test_session(tmp_path)
    with patch("app.database.SessionLocal", TestSession), \
         patch.dict(os.environ, {"DEMO_MODE": "false"}):
        _seed_demo_data()
    db = TestSession()
    try:
        assert db.query(Meal).count() == 0
    finally:
        db.close()


def test_demo_seed_skips_when_meals_exist(tmp_path):
    """Demo data should not be added when meals already exist."""
    TestSession = _make_test_session(tmp_path)
    # Pre-seed one meal
    db = TestSession()
    db.add(Meal(name="Existing Meal", meal_type="home_cooked"))
    db.commit()
    existing_count = db.query(Meal).count()
    db.close()

    with patch("app.database.SessionLocal", TestSession), \
         patch.dict(os.environ, {"DEMO_MODE": "true"}):
        _seed_demo_data()

    db = TestSession()
    try:
        assert db.query(Meal).count() == existing_count
    finally:
        db.close()


def test_demo_seed_updates_protein_quantities(tmp_path):
    """Demo mode should set protein inventory quantities."""
    TestSession = _make_test_session(tmp_path)
    with patch("app.database.SessionLocal", TestSession), \
         patch.dict(os.environ, {"DEMO_MODE": "true"}):
        _seed_proteins()
        _seed_demo_data()
    db = TestSession()
    try:
        for name, expected_qty in DEMO_PROTEIN_QUANTITIES.items():
            row = db.query(ProteinInventory).filter(
                ProteinInventory.protein_name == name
            ).first()
            assert row is not None, f"Protein {name} not found"
            assert row.quantity == expected_qty
    finally:
        db.close()


def test_demo_meals_have_variety():
    """Demo meal list should include a mix of types, proteins, and cuisines."""
    types = {m.get("meal_type") for m in DEMO_MEALS}
    assert "home_cooked" in types
    assert "eat_out" in types
    assert "frozen" in types
    assert "other" in types

    proteins = {m.get("protein") for m in DEMO_MEALS if m.get("protein")}
    assert len(proteins) >= 5, f"Expected at least 5 different proteins, got {proteins}"

    cuisines = {m.get("cuisine") for m in DEMO_MEALS if m.get("cuisine")}
    assert len(cuisines) >= 5, f"Expected at least 5 different cuisines, got {cuisines}"
