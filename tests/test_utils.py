from datetime import date
import pytest
from fastapi import HTTPException
from app.utils import DAY_NAMES, sunday_of, get_or_404
from app.models import Meal


def test_get_or_404_returns_object(db_session):
    """Create a meal via the ORM, then verify get_or_404 finds it."""
    meal = Meal(name="Test Pasta", meal_type="home_cooked", frozen_quantity=0, protein_servings=1)
    db_session.add(meal)
    db_session.commit()
    result = get_or_404(db_session, Meal, detail="Meal not found", id=meal.id)
    assert result.id == meal.id
    assert result.name == "Test Pasta"


def test_get_or_404_raises_404(db_session):
    """Verify get_or_404 raises HTTPException 404 for missing records."""
    with pytest.raises(HTTPException) as exc_info:
        get_or_404(db_session, Meal, detail="Meal not found", id=99999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Meal not found"


def test_sunday_of():
    # Wednesday 2026-04-01 -> Sunday 2026-03-29
    assert sunday_of(date(2026, 4, 1)) == date(2026, 3, 29)
    # Sunday itself -> same Sunday
    assert sunday_of(date(2026, 3, 29)) == date(2026, 3, 29)
    # Saturday 2026-04-04 -> Sunday 2026-03-29
    assert sunday_of(date(2026, 4, 4)) == date(2026, 3, 29)


def test_day_names():
    assert len(DAY_NAMES) == 7
    assert DAY_NAMES[0] == "Sunday"
    assert DAY_NAMES[6] == "Saturday"
