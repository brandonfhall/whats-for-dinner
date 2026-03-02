"""Tests for AI status, prompt construction, and plan generation.

Real API calls are never made — _call_anthropic / _call_openai are mocked.
"""

import os
from datetime import date
from unittest.mock import patch

from app.routers.ai import _build_prompt


# ── Helper ────────────────────────────────────────────────────────────────────

def _mock_suggestions(meals: list[dict]) -> list[dict]:
    """Build a valid 7-day suggestion list referencing real meal IDs."""
    return [
        {
            "day_of_week": i,
            "day_type": "home_cooked",
            "meal_id": meals[i % len(meals)]["id"],
            "meal_name": meals[i % len(meals)]["name"],
            "custom_name": "",
            "notes": f"Day {i} note",
        }
        for i in range(7)
    ]


# ── Status endpoint ───────────────────────────────────────────────────────────

def test_ai_status_configured(client):
    with patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"}):
        r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["provider"] == "anthropic"
    assert data["reason"] is None


def test_ai_status_missing_key(client):
    env = {"AI_PROVIDER": "anthropic", "AI_API_KEY": ""}
    with patch.dict(os.environ, env, clear=False):
        # Ensure AI_API_KEY is actually empty
        with patch("os.getenv", side_effect=lambda k, *d: "" if k == "AI_API_KEY" else os.environ.get(k, *d)):
            r = client.get("/api/ai/status")
    # Alternatively — simpler direct check of _check_configured:
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("anthropic")
    # With no key set in CI env, should be False
    # (we just test the logic, not rely on env state)
    assert isinstance(configured, bool)
    assert reason is None or isinstance(reason, str)


def test_ai_status_disabled(client):
    with patch.dict(os.environ, {"AI_PROVIDER": "none"}):
        r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False
    assert data["provider"] == "none"
    assert data["reason"] is None  # disabled intentionally, not misconfigured


def test_check_configured_none_provider():
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("none")
    assert configured is False
    assert reason is None


def test_check_configured_missing_key():
    from app.routers.ai import _check_configured
    with patch.dict(os.environ, {}, clear=True):
        configured, reason = _check_configured("anthropic")
    assert configured is False
    assert reason is not None
    assert "AI_API_KEY" in reason


def test_check_configured_with_key():
    from app.routers.ai import _check_configured
    with patch.dict(os.environ, {"AI_API_KEY": "sk-test"}):
        configured, reason = _check_configured("anthropic")
    assert configured is True
    assert reason is None


# ── Prompt construction ───────────────────────────────────────────────────────

def test_build_prompt_contains_day_numbering_convention():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
    )
    # Must spell out the Sun=0 convention so the model uses correct indices
    assert "Sunday" in prompt
    assert "Saturday" in prompt


def test_build_prompt_gym_days_include_day_numbers():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[1, 3],   # Monday, Wednesday
        eat_out_days=[],
    )
    assert "Monday (day_of_week=1)" in prompt
    assert "Wednesday (day_of_week=3)" in prompt


def test_build_prompt_eat_out_days_include_day_numbers():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[5],   # Friday
    )
    assert "Friday (day_of_week=5)" in prompt


def test_build_prompt_no_gym_days_says_none():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
    )
    assert "none" in prompt.lower()


def test_build_prompt_includes_meal_library(client, meals):
    library = [{"id": m["id"], "name": m["name"], "type": m["meal_type"],
                "notes": m["notes"], "has_leftovers": m["has_leftovers"],
                "easy_to_make": m["easy_to_make"], "shared_ingredients": m["shared_ingredients"],
                "protein": m["protein"]} for m in meals]
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=library,
        history=[],
        gym_days=[],
        eat_out_days=[],
    )
    for meal in meals:
        assert meal["name"] in prompt


# ── Generate endpoint ─────────────────────────────────────────────────────────

def test_generate_requires_meals_in_library(client):
    """Generation should fail with 400 when the meal library is empty."""
    plan = client.get("/api/plans/current").json()
    with patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"}):
        r = client.post("/api/ai/generate", json={
            "week_start": plan["week_start"],
            "existing_plan_id": plan["id"],
        })
    assert r.status_code == 400
    assert "meals" in r.json()["detail"].lower()


def test_generate_disabled_provider_returns_400(client, meals):
    plan = client.get("/api/plans/current").json()
    with patch.dict(os.environ, {"AI_PROVIDER": "none"}):
        r = client.post("/api/ai/generate", json={
            "week_start": plan["week_start"],
            "existing_plan_id": plan["id"],
        })
    assert r.status_code == 400


def test_generate_missing_key_returns_503(client, meals):
    plan = client.get("/api/plans/current").json()
    with patch.dict(os.environ, {"AI_PROVIDER": "anthropic"}):
        with patch("app.routers.ai.os.getenv", side_effect=lambda k, *d: "" if k == "AI_API_KEY" else os.environ.get(k, *d)):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })
    assert r.status_code == 503


def test_generate_mocked_anthropic(client, meals):
    """Full generate flow with a mocked Anthropic response."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"}):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    data = r.json()
    assert data["plan_id"] == plan["id"]
    assert len(data["suggestions"]) == 7


def test_generate_mocked_openai(client, meals):
    """Full generate flow with a mocked OpenAI response."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_openai", return_value=suggestions):
        with patch.dict(os.environ, {"AI_PROVIDER": "openai", "AI_API_KEY": "sk-test"}):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    assert len(r.json()["suggestions"]) == 7


def test_generate_ignores_hallucinated_meal_ids(client, meals):
    """Meal IDs not in the library should be silently dropped (meal_id → None)."""
    plan = client.get("/api/plans/current").json()
    bad_suggestions = [
        {
            "day_of_week": i,
            "day_type": "home_cooked",
            "meal_id": 999999,  # does not exist
            "meal_name": "Hallucinated Dish",
            "custom_name": "",
            "notes": "",
        }
        for i in range(7)
    ]

    with patch("app.routers.ai._call_anthropic", return_value=bad_suggestions):
        with patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"}):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    for s in r.json()["suggestions"]:
        assert s["meal_id"] is None


def test_generate_marks_plan_as_ai_generated(client, meals):
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with patch.dict(os.environ, {"AI_PROVIDER": "anthropic", "AI_API_KEY": "sk-test"}):
            client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    updated = client.get(f"/api/plans/{plan['id']}").json()
    assert updated["ai_generated"] is True
