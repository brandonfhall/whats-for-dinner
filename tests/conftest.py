"""Shared fixtures for the What's For Dinner test suite.

Each test gets a fresh in-memory SQLite database via the `client` fixture.
The production database is never touched during tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base, get_db
from app.main import app


MEAL_DEFAULTS = dict(
    notes="",
    recipe_url="",
    has_leftovers=False,
    easy_to_make=False,
    shared_ingredients="",
    protein="",
)


@pytest.fixture()
def client(tmp_path):
    """TestClient backed by a fresh per-test SQLite database."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app import models  # noqa — register ORM models with Base
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Patch init_db so the startup event doesn't touch the production database.
    with patch("app.main.init_db"):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


@pytest.fixture()
def meals(client):
    """Seed the meal library with five varied test meals."""
    seed = [
        {**MEAL_DEFAULTS, "name": "Chicken Stir Fry",   "meal_type": "home_cooked", "has_leftovers": True,  "easy_to_make": True,  "protein": "Chicken"},
        {**MEAL_DEFAULTS, "name": "Beef Tacos",          "meal_type": "home_cooked", "has_leftovers": False, "easy_to_make": True,  "protein": "Beef"},
        {**MEAL_DEFAULTS, "name": "Pasta Bolognese",     "meal_type": "home_cooked", "has_leftovers": True,  "easy_to_make": False, "protein": "Beef"},
        {**MEAL_DEFAULTS, "name": "Veggie Curry",        "meal_type": "home_cooked", "has_leftovers": True,  "easy_to_make": True,  "protein": "Tofu"},
        {**MEAL_DEFAULTS, "name": "Salmon Bowl",         "meal_type": "home_cooked", "has_leftovers": False, "easy_to_make": False, "protein": "Fish"},
    ]
    created = []
    for m in seed:
        r = client.post("/api/meals", json=m)
        assert r.status_code == 201, r.text
        created.append(r.json())
    return created
