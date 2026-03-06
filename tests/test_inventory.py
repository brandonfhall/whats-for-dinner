"""Tests for the protein inventory router (/api/inventory)."""


def test_list_proteins_empty(client):
    r = client.get("/api/inventory/proteins")
    assert r.status_code == 200
    assert r.json() == []


def test_create_protein(client):
    payload = {
        "protein_name": "Duck",
        "display_name": "Duck",
        "emoji": "🦆",
        "group": "meat",
        "quantity": 0,
        "unit": "servings",
    }
    r = client.post("/api/inventory/proteins", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["protein_name"] == "Duck"
    assert data["display_name"] == "Duck"
    assert data["emoji"] == "🦆"
    assert data["group"] == "meat"
    assert data["quantity"] == 0


def test_create_duplicate_protein_returns_409(client):
    payload = {"protein_name": "Chicken", "display_name": "Chicken"}
    r1 = client.post("/api/inventory/proteins", json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/inventory/proteins", json=payload)
    assert r2.status_code == 409


def test_update_protein_quantity(client):
    client.post("/api/inventory/proteins", json={"protein_name": "Beef", "display_name": "Beef"})
    r = client.put("/api/inventory/proteins/Beef", json={"quantity": 5})
    assert r.status_code == 200
    assert r.json()["quantity"] == 5


def test_adjust_protein_delta(client):
    client.post("/api/inventory/proteins", json={"protein_name": "Pork", "display_name": "Pork"})
    r = client.patch("/api/inventory/proteins/Pork/adjust?delta=3")
    assert r.status_code == 200
    assert r.json()["quantity"] == 3

    r = client.patch("/api/inventory/proteins/Pork/adjust?delta=-1")
    assert r.json()["quantity"] == 2


def test_adjust_protein_floor_at_zero(client):
    client.post("/api/inventory/proteins", json={"protein_name": "Tofu", "display_name": "Tofu"})
    r = client.patch("/api/inventory/proteins/Tofu/adjust?delta=-10")
    assert r.status_code == 200
    assert r.json()["quantity"] == 0


def test_delete_protein(client):
    client.post("/api/inventory/proteins", json={"protein_name": "Lamb", "display_name": "Lamb"})
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


def test_create_protein_negative_quantity_floors_at_zero(client):
    payload = {"protein_name": "Bison", "display_name": "Bison", "quantity": -5}
    r = client.post("/api/inventory/proteins", json=payload)
    assert r.status_code == 201
    assert r.json()["quantity"] == 0


def test_update_protein_negative_quantity_floors_at_zero(client):
    client.post("/api/inventory/proteins", json={"protein_name": "Elk", "display_name": "Elk"})
    r = client.put("/api/inventory/proteins/Elk", json={"quantity": -3})
    assert r.status_code == 200
    assert r.json()["quantity"] == 0
