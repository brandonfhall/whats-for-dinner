"""Tests for the meal library CRUD endpoints."""

from tests.conftest import MEAL_DEFAULTS


# ── Helpers ──────────────────────────────────────────────────────────────────

def create_meal(client, name="Test Pasta", **kwargs):
    payload = {**MEAL_DEFAULTS, "name": name, "meal_type": "home_cooked", **kwargs}
    r = client.post("/api/meals", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ── Create ────────────────────────────────────────────────────────────────────

def test_create_meal_returns_201(client):
    r = client.post("/api/meals", json={
        **MEAL_DEFAULTS,
        "name": "Spaghetti Bolognese",
        "meal_type": "home_cooked",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Spaghetti Bolognese"
    assert data["id"] is not None
    assert data["active"] is True


def test_create_meal_stores_all_fields(client):
    payload = {
        "name": "Thai Green Curry",
        "meal_type": "home_cooked",
        "notes": "Use coconut milk",
        "recipe_url": "https://example.com/recipe",
        "has_leftovers": True,
        "easy_to_make": True,
        "shared_ingredients": "Same chicken as tacos",
        "protein": "Chicken",
    }
    data = client.post("/api/meals", json=payload).json()
    for key, value in payload.items():
        assert data[key] == value, f"Field {key!r} mismatch"


def test_create_meal_missing_name_returns_422(client):
    r = client.post("/api/meals", json={**MEAL_DEFAULTS, "meal_type": "home_cooked"})
    assert r.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────

def test_list_meals_empty(client):
    r = client.get("/api/meals")
    assert r.status_code == 200
    assert r.json() == []


def test_list_meals_returns_all_active(client):
    create_meal(client, "Meal A")
    create_meal(client, "Meal B")
    r = client.get("/api/meals")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_meals_sorted_by_name(client):
    create_meal(client, "Zucchini Pasta")
    create_meal(client, "Apple Salad")
    create_meal(client, "Mango Chicken")
    names = [m["name"] for m in client.get("/api/meals").json()]
    assert names == sorted(names)


def test_list_meals_active_only_excludes_deleted(client):
    meal = create_meal(client, "Soon To Be Gone")
    client.delete(f"/api/meals/{meal['id']}")
    meals = client.get("/api/meals?active_only=true").json()
    assert all(m["id"] != meal["id"] for m in meals)


def test_list_meals_active_only_false_includes_deleted(client):
    meal = create_meal(client, "Deleted But Visible")
    client.delete(f"/api/meals/{meal['id']}")
    all_meals = client.get("/api/meals?active_only=false").json()
    ids = [m["id"] for m in all_meals]
    assert meal["id"] in ids


# ── Get ───────────────────────────────────────────────────────────────────────

def test_get_meal_by_id(client):
    meal = create_meal(client, "Ramen")
    r = client.get(f"/api/meals/{meal['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Ramen"


def test_get_meal_not_found_returns_404(client):
    r = client.get("/api/meals/99999")
    assert r.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_meal_name(client):
    meal = create_meal(client, "Old Name")
    r = client.put(f"/api/meals/{meal['id']}", json={**MEAL_DEFAULTS, "name": "New Name", "meal_type": "home_cooked"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_meal_protein_and_flags(client):
    meal = create_meal(client, "Fish Tacos")
    r = client.put(f"/api/meals/{meal['id']}", json={
        **MEAL_DEFAULTS,
        "name": "Fish Tacos",
        "meal_type": "home_cooked",
        "protein": "Fish",
        "easy_to_make": True,
        "has_leftovers": True,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["protein"] == "Fish"
    assert data["easy_to_make"] is True
    assert data["has_leftovers"] is True


def test_update_meal_not_found_returns_404(client):
    r = client.put("/api/meals/99999", json={**MEAL_DEFAULTS, "name": "Ghost", "meal_type": "home_cooked"})
    assert r.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

def test_delete_meal_returns_204(client):
    meal = create_meal(client, "Doomed Dish")
    r = client.delete(f"/api/meals/{meal['id']}")
    assert r.status_code == 204


def test_delete_meal_soft_deletes(client):
    """Deleted meals set active=False rather than being removed from the DB."""
    meal = create_meal(client, "Soft Deleted Dish")
    client.delete(f"/api/meals/{meal['id']}")
    # Still retrievable by ID
    r = client.get(f"/api/meals/{meal['id']}")
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_delete_meal_not_found_returns_404(client):
    r = client.delete("/api/meals/99999")
    assert r.status_code == 404


# ── Usage count ───────────────────────────────────────────────────────────────

def test_times_used_reflects_plan_assignments(client):
    """times_used increments each time a meal is assigned to a plan day."""
    meal = create_meal(client, "Usage Counter Dish")
    assert client.get(f"/api/meals/{meal['id']}").json()["times_used"] == 0

    plan = client.get("/api/plans/current").json()
    client.put(f"/api/plans/{plan['id']}/days/2", json={
        "day_type": "home_cooked", "meal_id": meal["id"],
        "custom_name": "", "notes": "", "carry_forward": False,
    })

    assert client.get(f"/api/meals/{meal['id']}").json()["times_used"] == 1

    # Assign the same meal to a second day — count should go to 2
    client.put(f"/api/plans/{plan['id']}/days/4", json={
        "day_type": "home_cooked", "meal_id": meal["id"],
        "custom_name": "", "notes": "", "carry_forward": False,
    })
    assert client.get(f"/api/meals/{meal['id']}").json()["times_used"] == 2


# ── Cuisine ───────────────────────────────────────────────────────────────────

def test_cuisine_stored_and_returned(client):
    meal = create_meal(client, "Carbonara", cuisine="Italian")
    assert meal["cuisine"] == "Italian"
    fetched = client.get(f"/api/meals/{meal['id']}").json()
    assert fetched["cuisine"] == "Italian"


def test_cuisine_default_empty_string(client):
    meal = create_meal(client, "Plain Chicken")
    assert meal["cuisine"] == ""


def test_update_meal_cuisine(client):
    meal = create_meal(client, "Tacos")
    r = client.put(f"/api/meals/{meal['id']}", json={**MEAL_DEFAULTS, "name": "Tacos", "cuisine": "Mexican"})
    assert r.status_code == 200
    assert r.json()["cuisine"] == "Mexican"
