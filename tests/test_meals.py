"""Tests for the meal library CRUD endpoints."""

from tests.conftest import MEAL_DEFAULTS


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


def test_list_meals_returns_all_active(client, create_meal_factory):
    create_meal_factory("Meal A")
    create_meal_factory("Meal B")
    r = client.get("/api/meals")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_meals_sorted_by_name(client, create_meal_factory):
    create_meal_factory("Zucchini Pasta")
    create_meal_factory("Apple Salad")
    create_meal_factory("Mango Chicken")
    names = [m["name"] for m in client.get("/api/meals").json()]
    assert names == sorted(names)


def test_list_meals_active_only_excludes_deleted(client, create_meal_factory):
    meal = create_meal_factory("Soon To Be Gone")
    client.delete(f"/api/meals/{meal['id']}")
    meals = client.get("/api/meals?active_only=true").json()
    assert all(m["id"] != meal["id"] for m in meals)


def test_list_meals_active_only_false_includes_deleted(client, create_meal_factory):
    meal = create_meal_factory("Deleted But Visible")
    client.delete(f"/api/meals/{meal['id']}")
    all_meals = client.get("/api/meals?active_only=false").json()
    ids = [m["id"] for m in all_meals]
    assert meal["id"] in ids


# ── Get ───────────────────────────────────────────────────────────────────────

def test_get_meal_by_id(client, create_meal_factory):
    meal = create_meal_factory("Ramen")
    r = client.get(f"/api/meals/{meal['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Ramen"


def test_get_meal_not_found_returns_404(client):
    r = client.get("/api/meals/99999")
    assert r.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_meal_name(client, create_meal_factory):
    meal = create_meal_factory("Old Name")
    r = client.put(f"/api/meals/{meal['id']}", json={**MEAL_DEFAULTS, "name": "New Name", "meal_type": "home_cooked"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_update_meal_protein_and_flags(client, create_meal_factory):
    meal = create_meal_factory("Fish Tacos")
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

def test_delete_meal_returns_204(client, create_meal_factory):
    meal = create_meal_factory("Doomed Dish")
    r = client.delete(f"/api/meals/{meal['id']}")
    assert r.status_code == 204


def test_delete_meal_soft_deletes(client, create_meal_factory):
    """Deleted meals set active=False rather than being removed from the DB."""
    meal = create_meal_factory("Soft Deleted Dish")
    client.delete(f"/api/meals/{meal['id']}")
    # Still retrievable by ID
    r = client.get(f"/api/meals/{meal['id']}")
    assert r.status_code == 200
    assert r.json()["active"] is False


def test_delete_meal_not_found_returns_404(client):
    r = client.delete("/api/meals/99999")
    assert r.status_code == 404


# ── Usage count ───────────────────────────────────────────────────────────────

def test_times_used_reflects_plan_assignments(client, create_meal_factory):
    """times_used increments each time a meal is assigned to a plan day."""
    meal = create_meal_factory("Usage Counter Dish")
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

def test_cuisine_stored_and_returned(client, create_meal_factory):
    meal = create_meal_factory("Carbonara", cuisine="Italian")
    assert meal["cuisine"] == "Italian"
    fetched = client.get(f"/api/meals/{meal['id']}").json()
    assert fetched["cuisine"] == "Italian"


def test_cuisine_default_empty_string(client, create_meal_factory):
    meal = create_meal_factory("Plain Chicken")
    assert meal["cuisine"] == ""


def test_update_meal_cuisine(client, create_meal_factory):
    meal = create_meal_factory("Tacos")
    r = client.put(f"/api/meals/{meal['id']}", json={**MEAL_DEFAULTS, "name": "Tacos", "cuisine": "Mexican"})
    assert r.status_code == 200
    assert r.json()["cuisine"] == "Mexican"


# ── Frozen meals ────────────────────────────────────────────────────────────

def test_create_frozen_meal(client):
    r = client.post("/api/meals", json={
        **MEAL_DEFAULTS,
        "name": "Homemade Lasagna",
        "meal_type": "frozen",
        "frozen_quantity": 3,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["meal_type"] == "frozen"
    assert data["frozen_quantity"] == 3


def test_frozen_quantity_default_zero(client, create_meal_factory):
    meal = create_meal_factory("Regular Chicken")
    assert meal["frozen_quantity"] == 0


def test_adjust_frozen_quantity_increment(client):
    meal = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Frozen Chili", "meal_type": "frozen", "frozen_quantity": 2,
    }).json()
    r = client.patch(f"/api/meals/{meal['id']}/frozen-quantity?delta=3")
    assert r.status_code == 200
    assert r.json()["frozen_quantity"] == 5


def test_adjust_frozen_quantity_decrement(client):
    meal = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Frozen Soup", "meal_type": "frozen", "frozen_quantity": 4,
    }).json()
    r = client.patch(f"/api/meals/{meal['id']}/frozen-quantity?delta=-2")
    assert r.status_code == 200
    assert r.json()["frozen_quantity"] == 2


def test_adjust_frozen_quantity_floor_at_zero(client):
    meal = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Frozen Stew", "meal_type": "frozen", "frozen_quantity": 1,
    }).json()
    r = client.patch(f"/api/meals/{meal['id']}/frozen-quantity?delta=-10")
    assert r.status_code == 200
    assert r.json()["frozen_quantity"] == 0


def test_adjust_frozen_quantity_not_found(client):
    r = client.patch("/api/meals/99999/frozen-quantity?delta=1")
    assert r.status_code == 404


# ── Protein servings ────────────────────────────────────────────────────────

def test_protein_servings_default_is_one(client, create_meal_factory):
    meal = create_meal_factory("Simple Meal")
    assert meal["protein_servings"] == 1


def test_create_meal_with_protein_servings(client):
    r = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Chicken Curry", "meal_type": "home_cooked",
        "protein": "Chicken", "protein_servings": 2,
    })
    assert r.status_code == 201
    assert r.json()["protein_servings"] == 2


def test_update_protein_servings(client, create_meal_factory):
    meal = create_meal_factory("Beef Stew")
    r = client.put(f"/api/meals/{meal['id']}", json={
        **MEAL_DEFAULTS, "name": "Beef Stew", "protein_servings": 3,
    })
    assert r.status_code == 200
    assert r.json()["protein_servings"] == 3


def test_create_meal_negative_frozen_quantity_rejected(client):
    r = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Bad Frozen", "meal_type": "frozen", "frozen_quantity": -5,
    })
    assert r.status_code == 422


def test_create_meal_negative_protein_servings_rejected(client):
    r = client.post("/api/meals", json={
        **MEAL_DEFAULTS, "name": "Bad Servings", "meal_type": "home_cooked", "protein_servings": -2,
    })
    assert r.status_code == 422


def test_update_meal_negative_frozen_quantity_rejected(client, create_meal_factory):
    meal = create_meal_factory("Lasagna", meal_type="frozen")
    r = client.put(f"/api/meals/{meal['id']}", json={
        **MEAL_DEFAULTS, "name": "Lasagna", "meal_type": "frozen", "frozen_quantity": -10,
    })
    assert r.status_code == 422


def test_update_meal_negative_protein_servings_rejected(client, create_meal_factory):
    meal = create_meal_factory("Curry")
    r = client.put(f"/api/meals/{meal['id']}", json={
        **MEAL_DEFAULTS, "name": "Curry", "protein_servings": -3,
    })
    assert r.status_code == 422
