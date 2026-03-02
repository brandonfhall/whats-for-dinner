"""Tests for the key-value settings store."""


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_get_settings_returns_defaults(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["gym_days"] == []
    assert data["eat_out_days"] == []
    assert data["ai_provider"] == "anthropic"


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_gym_days(client):
    r = client.put("/api/settings", json={"gym_days": [1, 3]})
    assert r.status_code == 200
    assert r.json()["gym_days"] == [1, 3]


def test_update_eat_out_days(client):
    r = client.put("/api/settings", json={"eat_out_days": [5, 6]})
    assert r.status_code == 200
    assert r.json()["eat_out_days"] == [5, 6]


def test_update_ai_provider(client):
    r = client.put("/api/settings", json={"ai_provider": "openai"})
    assert r.status_code == 200
    assert r.json()["ai_provider"] == "openai"


def test_settings_persist_across_requests(client):
    client.put("/api/settings", json={"gym_days": [0, 2, 4]})
    r = client.get("/api/settings")
    assert r.json()["gym_days"] == [0, 2, 4]


def test_partial_update_leaves_other_fields_unchanged(client):
    """Updating one field should not reset others."""
    client.put("/api/settings", json={"gym_days": [1], "eat_out_days": [5]})
    # Update only gym_days
    client.put("/api/settings", json={"gym_days": [2]})
    data = client.get("/api/settings").json()
    assert data["gym_days"] == [2]
    assert data["eat_out_days"] == [5]


def test_clear_gym_days(client):
    client.put("/api/settings", json={"gym_days": [1, 3]})
    r = client.put("/api/settings", json={"gym_days": []})
    assert r.json()["gym_days"] == []


def test_gym_and_eat_out_can_overlap(client):
    """The API doesn't enforce mutual exclusivity — the UI handles that."""
    r = client.put("/api/settings", json={"gym_days": [5], "eat_out_days": [5]})
    assert r.status_code == 200
    data = r.json()
    assert 5 in data["gym_days"]
    assert 5 in data["eat_out_days"]
