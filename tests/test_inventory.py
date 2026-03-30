"""Tests for the protein inventory router (/api/inventory)."""


def test_list_proteins_empty(client):
    r = client.get("/api/inventory/proteins")
    assert r.status_code == 200
    assert r.json() == []


def test_create_protein(create_protein_factory):
    protein = create_protein_factory(
        name="Duck",
        display_name="Duck",
        emoji="🦆",
        group="meat",
        quantity=0,
        unit="servings",
    )
    assert protein["protein_name"] == "Duck"
    assert protein["display_name"] == "Duck"
    assert protein["emoji"] == "🦆"
    assert protein["group"] == "meat"
    assert protein["quantity"] == 0


def test_create_duplicate_protein_returns_409(client, create_protein_factory):
    create_protein_factory(name="Chicken", display_name="Chicken")
    r2 = client.post("/api/inventory/proteins", json={"protein_name": "Chicken", "display_name": "Chicken"})
    assert r2.status_code == 409


def test_update_protein_quantity(client, create_protein_factory):
    create_protein_factory(name="Beef", display_name="Beef")
    r = client.put("/api/inventory/proteins/Beef", json={"quantity": 5})
    assert r.status_code == 200
    assert r.json()["quantity"] == 5


def test_adjust_protein_delta(client, create_protein_factory):
    create_protein_factory(name="Pork", display_name="Pork")
    r = client.patch("/api/inventory/proteins/Pork/adjust?delta=3")
    assert r.status_code == 200
    assert r.json()["quantity"] == 3

    r = client.patch("/api/inventory/proteins/Pork/adjust?delta=-1")
    assert r.json()["quantity"] == 2


def test_adjust_protein_floor_at_zero(client, create_protein_factory):
    create_protein_factory(name="Tofu", display_name="Tofu")
    r = client.patch("/api/inventory/proteins/Tofu/adjust?delta=-10")
    assert r.status_code == 200
    assert r.json()["quantity"] == 0


def test_delete_protein(client, create_protein_factory):
    create_protein_factory(name="Lamb", display_name="Lamb")
    r = client.delete("/api/inventory/proteins/Lamb")
    assert r.status_code == 204

    r = client.get("/api/inventory/proteins")
    assert all(p["protein_name"] != "Lamb" for p in r.json())


def test_delete_nonexistent_protein_returns_404(client):
    r = client.delete("/api/inventory/proteins/Nonexistent")
    assert r.status_code == 404


def test_adjust_nonexistent_protein_returns_404(client):
    r = client.patch("/api/inventory/proteins/Nonexistent/adjust?delta=1")
    assert r.status_code == 404


def test_create_protein_negative_quantity_rejected(client):
    payload = {"protein_name": "Bison", "display_name": "Bison", "quantity": -5}
    r = client.post("/api/inventory/proteins", json=payload)
    assert r.status_code == 422


def test_update_protein_not_found_returns_404(client):
    r = client.put("/api/inventory/proteins/Nonexistent", json={"quantity": 5})
    assert r.status_code == 404


def test_update_protein_negative_quantity_rejected(client, create_protein_factory):
    create_protein_factory(name="Elk", display_name="Elk")
    r = client.put("/api/inventory/proteins/Elk", json={"quantity": -3})
    assert r.status_code == 422


def test_update_protein_emoji(client, create_protein_factory):
    create_protein_factory(name="Steak", display_name="Steak", emoji="🟢", group="meat")
    r = client.put("/api/inventory/proteins/Steak", json={"emoji": "🥩"})
    assert r.status_code == 200
    assert r.json()["emoji"] == "🥩"


def test_update_protein_group(client, create_protein_factory):
    create_protein_factory(name="Tempeh", display_name="Tempeh", group="meat")
    r = client.put("/api/inventory/proteins/Tempeh", json={"group": "veg"})
    assert r.status_code == 200
    assert r.json()["group"] == "veg"


def test_update_protein_emoji_and_group_together(client, create_protein_factory):
    create_protein_factory(name="Tofu2", display_name="Tofu", emoji="❓", group="meat")
    r = client.put("/api/inventory/proteins/Tofu2", json={"emoji": "🫘", "group": "veg"})
    assert r.status_code == 200
    data = r.json()
    assert data["emoji"] == "🫘"
    assert data["group"] == "veg"
