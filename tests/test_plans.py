"""Tests for weekly plan creation, week navigation, and carry-forward logic."""

from datetime import date, timedelta

import pytest

from app.routers.plans import _sunday_of


# ── Unit tests: _sunday_of helper ────────────────────────────────────────────

def test_sunday_of_on_sunday():
    """A Sunday should return itself."""
    d = date(2026, 3, 1)  # Sunday
    assert _sunday_of(d) == date(2026, 3, 1)


def test_sunday_of_on_monday():
    """Monday should roll back to the previous Sunday."""
    d = date(2026, 3, 2)  # Monday
    assert _sunday_of(d) == date(2026, 3, 1)


def test_sunday_of_on_saturday():
    """Saturday should roll back to the Sunday 6 days prior."""
    d = date(2026, 3, 7)  # Saturday
    assert _sunday_of(d) == date(2026, 3, 1)


def test_sunday_of_idempotent():
    """Calling _sunday_of on a result already a Sunday returns the same date."""
    sunday = _sunday_of(date(2026, 3, 4))
    assert _sunday_of(sunday) == sunday


# ── Current plan ──────────────────────────────────────────────────────────────

def test_current_plan_auto_creates(client):
    r = client.get("/api/plans/current")
    assert r.status_code == 200
    plan = r.json()
    assert plan["id"] is not None
    assert len(plan["days"]) == 7


def test_current_plan_week_start_is_sunday(client):
    r = client.get("/api/plans/current")
    week_start = date.fromisoformat(r.json()["week_start"])
    assert week_start.weekday() == 6  # Sunday in Python's weekday() is 6


def test_current_plan_idempotent(client):
    """Fetching /current twice returns the same plan."""
    id1 = client.get("/api/plans/current").json()["id"]
    id2 = client.get("/api/plans/current").json()["id"]
    assert id1 == id2


def test_current_plan_defaults_to_draft(client):
    plan = client.get("/api/plans/current").json()
    assert plan["status"] == "draft"
    assert plan["ai_generated"] is False


# ── Week navigation ───────────────────────────────────────────────────────────

def test_week_endpoint_auto_creates_new_week(client):
    current = client.get("/api/plans/current").json()
    next_sunday = date.fromisoformat(current["week_start"]) + timedelta(weeks=1)
    r = client.get(f"/api/plans/week/{next_sunday.isoformat()}")
    assert r.status_code == 200
    assert r.json()["week_start"] == next_sunday.isoformat()


def test_week_endpoint_returns_existing_plan(client):
    """Navigating to the same week twice returns the same plan ID."""
    current = client.get("/api/plans/current").json()
    week_start = current["week_start"]
    id_a = client.get(f"/api/plans/week/{week_start}").json()["id"]
    id_b = client.get(f"/api/plans/week/{week_start}").json()["id"]
    assert id_a == id_b


def test_week_endpoint_normalises_to_sunday(client):
    """Passing any day of the week snaps to the Sunday of that week."""
    # 2026-03-04 is a Wednesday — should snap to 2026-03-01 (Sunday)
    r = client.get("/api/plans/week/2026-03-04")
    assert r.status_code == 200
    assert r.json()["week_start"] == "2026-03-01"


def test_previous_week_auto_creates(client):
    current = client.get("/api/plans/current").json()
    prev_sunday = date.fromisoformat(current["week_start"]) - timedelta(weeks=1)
    r = client.get(f"/api/plans/week/{prev_sunday.isoformat()}")
    assert r.status_code == 200
    assert r.json()["week_start"] == prev_sunday.isoformat()


def test_new_week_has_seven_days(client):
    current = client.get("/api/plans/current").json()
    next_sunday = date.fromisoformat(current["week_start"]) + timedelta(weeks=1)
    plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()
    assert len(plan["days"]) == 7
    day_numbers = sorted(d["day_of_week"] for d in plan["days"])
    assert day_numbers == list(range(7))


# ── Gym / eat-out pre-population ──────────────────────────────────────────────

def test_gym_days_pre_populated_as_home_cooked(client):
    """Days configured as gym nights are created with day_type=home_cooked."""
    client.put("/api/settings", json={"gym_days": [1, 3], "eat_out_days": [], "ai_provider": "none"})
    current = client.get("/api/plans/current").json()
    next_sunday = date.fromisoformat(current["week_start"]) + timedelta(weeks=1)
    plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    days_by_dow = {d["day_of_week"]: d for d in plan["days"]}
    assert days_by_dow[1]["day_type"] == "home_cooked"
    assert days_by_dow[3]["day_type"] == "home_cooked"


def test_eat_out_days_pre_populated(client):
    """Days configured as eat-out nights are created with day_type=eat_out."""
    client.put("/api/settings", json={"gym_days": [], "eat_out_days": [5], "ai_provider": "none"})
    current = client.get("/api/plans/current").json()
    next_sunday = date.fromisoformat(current["week_start"]) + timedelta(weeks=1)
    plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    friday = next(d for d in plan["days"] if d["day_of_week"] == 5)
    assert friday["day_type"] == "eat_out"


def test_unconfigured_days_default_to_skip(client):
    client.put("/api/settings", json={"gym_days": [], "eat_out_days": [], "ai_provider": "none"})
    current = client.get("/api/plans/current").json()
    next_sunday = date.fromisoformat(current["week_start"]) + timedelta(weeks=1)
    plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    assert all(d["day_type"] == "skip" for d in plan["days"])


# ── Update day ────────────────────────────────────────────────────────────────

def test_update_day_sets_meal(client, meals):
    plan = client.get("/api/plans/current").json()
    meal = meals[0]
    r = client.put(f"/api/plans/{plan['id']}/days/2", json={
        "day_type": "home_cooked",
        "meal_id": meal["id"],
        "custom_name": "",
        "notes": "",
        "carry_forward": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["meal_id"] == meal["id"]
    assert data["meal"]["name"] == meal["name"]


def test_update_day_eat_out_clears_meal(client, meals):
    """Switching to eat_out should clear any meal_id."""
    plan = client.get("/api/plans/current").json()
    # First set a meal
    client.put(f"/api/plans/{plan['id']}/days/2", json={
        "day_type": "home_cooked", "meal_id": meals[0]["id"],
        "custom_name": "", "notes": "", "carry_forward": False,
    })
    # Switch to eat_out
    r = client.put(f"/api/plans/{plan['id']}/days/2", json={
        "day_type": "eat_out", "meal_id": None,
        "custom_name": "Chipotle", "notes": "", "carry_forward": False,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["meal_id"] is None
    assert data["custom_name"] == "Chipotle"


def test_update_day_invalid_dow_returns_422(client):
    plan = client.get("/api/plans/current").json()
    r = client.put(f"/api/plans/{plan['id']}/days/7", json={
        "day_type": "skip", "meal_id": None,
        "custom_name": "", "notes": "", "carry_forward": False,
    })
    assert r.status_code == 422


# ── Carry-forward ─────────────────────────────────────────────────────────────

def test_carry_forward_flag_persists(client, meals):
    plan = client.get("/api/plans/current").json()
    r = client.put(f"/api/plans/{plan['id']}/days/4", json={
        "day_type": "home_cooked", "meal_id": meals[0]["id"],
        "custom_name": "", "notes": "", "carry_forward": True,
    })
    assert r.status_code == 200
    assert r.json()["carry_forward"] is True


def test_carry_forward_propagates_meal_to_next_week(client, meals):
    """A pinned day propagates its meal to the same day of the following week."""
    plan = client.get("/api/plans/current").json()
    meal = meals[0]
    week_start = plan["week_start"]

    # Pin Thursday (day 4) in the current week
    client.put(f"/api/plans/{plan['id']}/days/4", json={
        "day_type": "home_cooked", "meal_id": meal["id"],
        "custom_name": "", "notes": "", "carry_forward": True,
    })

    # Navigate to next week (fresh — never created)
    next_sunday = date.fromisoformat(week_start) + timedelta(weeks=1)
    next_plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    thursday = next(d for d in next_plan["days"] if d["day_of_week"] == 4)
    assert thursday["meal_id"] == meal["id"]
    assert thursday["carry_forward"] is True  # pin propagates


def test_carry_forward_does_not_overwrite_gym_day(client, meals):
    """Gym days are home_cooked (not skip), so carry-forward skips them."""
    client.put("/api/settings", json={"gym_days": [1], "eat_out_days": [], "ai_provider": "none"})

    plan = client.get("/api/plans/current").json()
    week_start = plan["week_start"]

    # Pin Monday (day 1, a gym night) with a specific meal
    client.put(f"/api/plans/{plan['id']}/days/1", json={
        "day_type": "home_cooked", "meal_id": meals[0]["id"],
        "custom_name": "", "notes": "", "carry_forward": True,
    })

    next_sunday = date.fromisoformat(week_start) + timedelta(weeks=1)
    next_plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    monday = next(d for d in next_plan["days"] if d["day_of_week"] == 1)
    # Gym day is pre-set to home_cooked but carry-forward does not fill the meal
    # (carry-forward only fills days that are still skip)
    assert monday["day_type"] == "home_cooked"
    assert monday["meal_id"] is None


def test_carry_forward_false_does_not_propagate(client, meals):
    """Days without carry_forward set should not appear in the next week."""
    plan = client.get("/api/plans/current").json()
    week_start = plan["week_start"]

    client.put(f"/api/plans/{plan['id']}/days/6", json={
        "day_type": "home_cooked", "meal_id": meals[1]["id"],
        "custom_name": "", "notes": "", "carry_forward": False,
    })

    next_sunday = date.fromisoformat(week_start) + timedelta(weeks=1)
    next_plan = client.get(f"/api/plans/week/{next_sunday.isoformat()}").json()

    saturday = next(d for d in next_plan["days"] if d["day_of_week"] == 6)
    assert saturday["meal_id"] is None
    assert saturday["day_type"] == "skip"


# ── Delete plan ───────────────────────────────────────────────────────────────

def test_delete_plan(client):
    plan = client.get("/api/plans/current").json()
    plan_id = plan["id"]

    r = client.delete(f"/api/plans/{plan_id}")
    assert r.status_code == 204

    r = client.get(f"/api/plans/{plan_id}")
    assert r.status_code == 404


def test_delete_plan_not_found_returns_404(client):
    r = client.delete("/api/plans/99999")
    assert r.status_code == 404
