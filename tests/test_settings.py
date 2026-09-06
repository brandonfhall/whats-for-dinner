"""Tests for the key-value settings store."""

import os
from unittest.mock import patch


# ── Defaults ──────────────────────────────────────────────────────────────────

def test_get_settings_returns_defaults(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["gym_days"] == []
    assert data["eat_out_days"] == []
    assert data["ai_provider"] == "anthropic"
    assert data["ai_base_url"] == ""


def test_get_settings_ai_key_not_exposed(client):
    """The raw API key must never appear in GET /settings responses."""
    client.put("/api/settings", json={"ai_api_key": "sk-secret-123"})
    r = client.get("/api/settings")
    assert "ai_api_key" not in r.json()
    assert "sk-secret-123" not in r.text


def test_ai_key_configured_false_by_default(client):
    with patch.dict(os.environ, {}, clear=True):
        r = client.get("/api/settings")
    assert r.json()["ai_key_configured"] is False


def test_ai_key_configured_true_after_save(client):
    r = client.put("/api/settings", json={"ai_api_key": "sk-ant-test"})
    assert r.status_code == 200
    assert r.json()["ai_key_configured"] is True
    assert "ai_api_key" not in r.json()


def test_ai_key_configured_true_via_env(client):
    with patch.dict(os.environ, {"AI_API_KEY": "sk-env-key"}):
        r = client.get("/api/settings")
    assert r.json()["ai_key_configured"] is True


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


def test_update_ai_base_url(client):
    r = client.put("/api/settings", json={
        "ai_provider": "openai_compatible",
        "ai_base_url": "https://litellm.home/v1",
    })
    assert r.status_code == 200
    assert r.json()["ai_base_url"] == "https://litellm.home/v1"


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


# ── Custom instructions ──────────────────────────────────────────────────────

def test_get_settings_returns_empty_custom_instructions(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["custom_instructions"] == ""


def test_update_custom_instructions(client):
    r = client.put("/api/settings", json={"custom_instructions": "We prefer spicy food"})
    assert r.status_code == 200
    assert r.json()["custom_instructions"] == "We prefer spicy food"


def test_custom_instructions_persist_across_requests(client):
    client.put("/api/settings", json={"custom_instructions": "No dairy"})
    r = client.get("/api/settings")
    assert r.json()["custom_instructions"] == "No dairy"


def test_custom_instructions_update_leaves_other_fields_unchanged(client):
    client.put("/api/settings", json={"gym_days": [1], "custom_instructions": "Vegetarian"})
    client.put("/api/settings", json={"custom_instructions": "Vegan"})
    data = client.get("/api/settings").json()
    assert data["custom_instructions"] == "Vegan"
    assert data["gym_days"] == [1]


# ── AI model overrides ───────────────────────────────────────────────────────

def test_get_settings_returns_empty_model_overrides(client):
    """All three model fields default to blank, meaning \"use the built-in default\"."""
    data = client.get("/api/settings").json()
    assert data["ai_model_anthropic"] == ""
    assert data["ai_model_openai"] == ""
    assert data["ai_model_openai_compatible"] == ""


def test_update_model_overrides_round_trip(client):
    r = client.put("/api/settings", json={
        "ai_model_anthropic": "claude-opus-4-6",
        "ai_model_openai": "gpt-5",
        "ai_model_openai_compatible": "local-llama",
    })
    assert r.status_code == 200
    data = client.get("/api/settings").json()
    assert data["ai_model_anthropic"] == "claude-opus-4-6"
    assert data["ai_model_openai"] == "gpt-5"
    assert data["ai_model_openai_compatible"] == "local-llama"


def test_model_overrides_are_per_provider(client):
    """Setting one provider's model leaves the others alone — switching provider
    must not send a model name the new provider doesn't recognise."""
    client.put("/api/settings", json={"ai_model_anthropic": "claude-opus-4-6"})
    data = client.get("/api/settings").json()
    assert data["ai_model_openai"] == ""
    assert data["ai_model_openai_compatible"] == ""


def test_model_override_can_be_cleared(client):
    """Clearing the field stores "" so resolution falls back to the built-in default."""
    client.put("/api/settings", json={"ai_model_anthropic": "claude-opus-4-6"})
    client.put("/api/settings", json={"ai_model_anthropic": ""})
    assert client.get("/api/settings").json()["ai_model_anthropic"] == ""


# ── Resilience ───────────────────────────────────────────────────────────────

def test_corrupt_settings_json_returns_defaults(client_with_db):
    """A corrupt (non-JSON) value in the DB should be silently skipped; defaults returned."""
    from app.models import Setting
    client, db = client_with_db
    db.add(Setting(key="gym_days", value="not-valid-json{{"))
    db.commit()
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["gym_days"] == []  # default, not the corrupt value
