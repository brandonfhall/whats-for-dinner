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

def test_ai_status_configured(client, ai_env):
    with ai_env:
        r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["provider"] == "anthropic"
    assert data["reason"] is None


def test_ai_status_configured_via_db_key(client):
    """AI is configured when the key is stored in settings DB (no env var)."""
    with patch.dict(os.environ, {"AI_PROVIDER": "anthropic"}, clear=True):
        client.put("/api/settings", json={"ai_api_key": "sk-db-key"})
        r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is True
    assert data["reason"] is None


def test_ai_status_missing_key(client):
    """Status endpoint reports not-configured when AI_API_KEY is absent."""
    with patch("app.routers.ai.os.getenv", side_effect=lambda k, *d: "anthropic" if k == "AI_PROVIDER" else ""):
        r = client.get("/api/ai/status")
    assert r.status_code == 200
    data = r.json()
    assert data["configured"] is False
    assert data["provider"] == "anthropic"
    assert data["reason"] is not None
    assert "AI_API_KEY" in data["reason"]


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
    configured, reason = _check_configured("none", "")
    assert configured is False
    assert reason is None


def test_check_configured_missing_key():
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("anthropic", "")
    assert configured is False
    assert reason is not None
    assert "AI_API_KEY" in reason


def test_check_configured_with_key():
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("anthropic", "sk-test")
    assert configured is True
    assert reason is None


def test_check_configured_openai_compatible_missing_base_url():
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("openai_compatible", "sk-test", "")
    assert configured is False
    assert reason is not None
    assert "AI_BASE_URL" in reason


def test_check_configured_openai_compatible_with_base_url():
    from app.routers.ai import _check_configured
    configured, reason = _check_configured("openai_compatible", "sk-test", "https://litellm.home/v1")
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

def test_generate_requires_meals_in_library(client, ai_env):
    """Generation should fail with 400 when the meal library is empty."""
    plan = client.get("/api/plans/current").json()
    with ai_env:
        r = client.post("/api/ai/generate", json={
            "week_start": plan["week_start"],
            "existing_plan_id": plan["id"],
        })
    assert r.status_code == 400
    assert "meals" in r.json()["detail"].lower()


def test_generate_disabled_provider_returns_503(client, meals):
    plan = client.get("/api/plans/current").json()
    with patch.dict(os.environ, {"AI_PROVIDER": "none"}):
        r = client.post("/api/ai/generate", json={
            "week_start": plan["week_start"],
            "existing_plan_id": plan["id"],
        })
    assert r.status_code == 503


def test_generate_missing_key_returns_503(client, meals):
    plan = client.get("/api/plans/current").json()
    with patch.dict(os.environ, {"AI_PROVIDER": "anthropic"}):
        with patch("app.routers.ai.os.getenv", side_effect=lambda k, *d: "" if k == "AI_API_KEY" else os.environ.get(k, *d)):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })
    assert r.status_code == 503


def test_generate_mocked_anthropic(client, meals, ai_env):
    """Full generate flow with a mocked Anthropic response."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    data = r.json()
    assert data["plan_id"] == plan["id"]
    assert len(data["suggestions"]) == 7


def test_generate_mocked_openai(client, meals, ai_env):
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


def test_generate_mocked_openai_compatible(client, meals):
    """Full generate flow with a mocked self-hosted OpenAI-compatible response."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_openai_compatible", return_value=suggestions):
        with patch.dict(os.environ, {
            "AI_PROVIDER": "openai_compatible",
            "AI_API_KEY": "sk-test",
            "AI_BASE_URL": "https://litellm.home/v1",
        }):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    assert len(r.json()["suggestions"]) == 7


def test_generate_openai_compatible_empty_response_returns_500_with_clear_message(client, meals):
    """Reproduces the real failure: a reasoning model returns empty content because it
    spent the whole max_tokens budget on hidden reasoning — should surface a clear
    500 error, not the raw JSONDecodeError ("Expecting value: line 1 column 1")."""
    plan = client.get("/api/plans/current").json()

    error = ValueError("Model returned an empty response. Try raising AI_MAX_TOKENS_OPENAI_COMPATIBLE.")
    with patch("app.routers.ai._call_openai_compatible", side_effect=error):
        with patch.dict(os.environ, {
            "AI_PROVIDER": "openai_compatible",
            "AI_API_KEY": "sk-test",
            "AI_BASE_URL": "https://litellm.home/v1",
        }):
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 500
    assert "AI_MAX_TOKENS_OPENAI_COMPATIBLE" in r.json()["detail"]


def test_generate_openai_compatible_missing_base_url_returns_503(client, meals):
    """Without AI_BASE_URL, the openai_compatible provider is treated as not configured."""
    plan = client.get("/api/plans/current").json()

    with patch.dict(os.environ, {"AI_PROVIDER": "openai_compatible", "AI_API_KEY": "sk-test"}, clear=True):
        r = client.post("/api/ai/generate", json={
            "week_start": plan["week_start"],
            "existing_plan_id": plan["id"],
        })

    assert r.status_code == 503
    assert "AI_BASE_URL" in r.json()["detail"]


def test_generate_ignores_hallucinated_meal_ids(client, meals, ai_env):
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
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    for s in r.json()["suggestions"]:
        assert s["meal_id"] is None


def test_generate_marks_plan_as_ai_generated(client, meals, ai_env):
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    updated = client.get(f"/api/plans/{plan['id']}").json()
    assert updated["ai_generated"] is True


def test_generate_creates_plan_when_no_existing_plan_id(client, meals, ai_env):
    """Omitting existing_plan_id causes generate to create the plan automatically."""
    current = client.get("/api/plans/current").json()
    from datetime import timedelta
    next_sunday = (date.fromisoformat(current["week_start"]) + timedelta(weeks=2)).isoformat()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={"week_start": next_sunday})

    assert r.status_code == 200
    data = r.json()
    assert data["plan_id"] is not None
    assert len(data["suggestions"]) == 7


# ── Prompt mode ───────────────────────────────────────────────────────────────

def test_build_prompt_mix_mode_favours_less_used():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        mode="mix",
    )
    assert "Mix It Up" in prompt
    assert "4×" in prompt


def test_build_prompt_safe_mode_favours_favourites():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        mode="safe",
    )
    assert "Play It Safe" in prompt
    assert "3×" in prompt


def test_build_prompt_on_hand_mode():
    protein_inv = [
        {"protein_name": "Chicken", "quantity": 3, "unit": "servings"},
    ]
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        mode="on_hand",
        protein_inventory=protein_inv,
    )
    assert "On Hand" in prompt
    assert "PROTEIN INVENTORY" in prompt
    assert "Chicken" in prompt


def test_build_prompt_on_hand_includes_frozen_quantity():
    library = [{"id": 1, "name": "Frozen Chili", "type": "frozen",
                "frozen_quantity": 3, "protein_servings": 1,
                "notes": "", "has_leftovers": False, "easy_to_make": False,
                "shared_ingredients": "", "protein": "", "cuisine": "",
                "usage_count": 0}]
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=library,
        history=[],
        gym_days=[],
        eat_out_days=[],
        mode="on_hand",
    )
    assert "frozen_quantity" in prompt
    assert "Frozen Chili" in prompt


def test_build_prompt_includes_custom_instructions():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        custom_instructions="We prefer spicy food. Avoid dairy.",
    )
    assert "ADDITIONAL USER INSTRUCTIONS" in prompt
    assert "We prefer spicy food. Avoid dairy." in prompt


def test_build_prompt_omits_empty_custom_instructions():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        custom_instructions="",
    )
    assert "ADDITIONAL USER INSTRUCTIONS" not in prompt


def test_build_prompt_omits_whitespace_only_custom_instructions():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        custom_instructions="   ",
    )
    assert "ADDITIONAL USER INSTRUCTIONS" not in prompt


def test_build_prompt_includes_current_week_context():
    context = {
        "week_notes": "Guests visiting Thursday",
        "day_notes": [
            {"day": "Monday", "notes": "Use up leftover chicken"},
        ],
    }
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        current_week_context=context,
    )
    assert "CURRENT WEEK CONTEXT" in prompt
    assert "Guests visiting Thursday" in prompt
    assert "Monday: Use up leftover chicken" in prompt


def test_build_prompt_omits_week_context_when_none():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
        current_week_context=None,
    )
    assert "CURRENT WEEK CONTEXT" not in prompt


def test_generate_prefixes_ai_notes(client, meals, ai_env):
    """AI-generated notes should be prefixed with 'AI - '."""
    plan = client.get("/api/plans/current").json()
    suggestions = [
        {
            "day_of_week": i,
            "day_type": "home_cooked",
            "meal_id": meals[0]["id"],
            "meal_name": meals[0]["name"],
            "custom_name": "",
            "notes": "Great with rice" if i == 0 else "",
        }
        for i in range(7)
    ]

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    day0 = [s for s in r.json()["suggestions"] if s["day_of_week"] == 0][0]
    assert day0["notes"] == "AI - Great with rice"
    # Days with no AI notes should have empty notes
    day1 = [s for s in r.json()["suggestions"] if s["day_of_week"] == 1][0]
    assert day1["notes"] == ""


def test_generate_preserves_existing_notes(client, meals, ai_env):
    """Existing day notes must be preserved; AI notes appended on a new line."""
    plan = client.get("/api/plans/current").json()
    # Set an existing note on Sunday (day 0)
    client.put(f"/api/plans/{plan['id']}/days/0", json={
        "day_type": "home_cooked",
        "meal_id": meals[0]["id"],
        "notes": "User note here",
    })

    suggestions = [
        {
            "day_of_week": i,
            "day_type": "home_cooked",
            "meal_id": meals[0]["id"],
            "meal_name": meals[0]["name"],
            "custom_name": "",
            "notes": "Pairs well with salad" if i == 0 else "",
        }
        for i in range(7)
    ]

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    day0 = [s for s in r.json()["suggestions"] if s["day_of_week"] == 0][0]
    assert "User note here" in day0["notes"]
    assert "AI - Pairs well with salad" in day0["notes"]
    assert day0["notes"] == "User note here\nAI - Pairs well with salad"


def test_generate_keeps_existing_notes_when_ai_has_none(client, meals, ai_env):
    """When AI returns empty notes, existing day notes should not be erased."""
    plan = client.get("/api/plans/current").json()
    client.put(f"/api/plans/{plan['id']}/days/2", json={
        "day_type": "home_cooked",
        "meal_id": meals[0]["id"],
        "notes": "Important user note",
    })

    suggestions = [
        {
            "day_of_week": i,
            "day_type": "home_cooked",
            "meal_id": meals[0]["id"],
            "meal_name": meals[0]["name"],
            "custom_name": "",
            "notes": "",
        }
        for i in range(7)
    ]

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    day2 = [s for s in r.json()["suggestions"] if s["day_of_week"] == 2][0]
    assert day2["notes"] == "Important user note"


def test_build_prompt_instructs_ai_not_to_repeat_notes():
    prompt = _build_prompt(
        week_start=date(2026, 3, 8),
        library=[],
        history=[],
        gym_days=[],
        eat_out_days=[],
    )
    assert "Do NOT repeat any existing day notes" in prompt


def test_generate_on_hand_mode_mocked(client, meals, ai_env):
    """Full generate flow with on_hand mode using mocked AI."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
                "mode": "on_hand",
            })

    assert r.status_code == 200
    assert len(r.json()["suggestions"]) == 7


def test_generate_ai_provider_error_returns_502(client, meals, ai_env):
    """When the AI provider raises a generic error (e.g. network), generate returns 502."""
    plan = client.get("/api/plans/current").json()

    with patch("app.routers.ai._call_anthropic", side_effect=RuntimeError("API unavailable")):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 502
    assert "API unavailable" in r.json()["detail"]


def test_generate_invalid_existing_plan_id_returns_404(client, meals, ai_env):
    """When existing_plan_id doesn't exist, generate returns 404."""
    plan = client.get("/api/plans/current").json()
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": 99999,
            })

    assert r.status_code == 404


def test_generate_eat_out_and_skip_day_types(client, meals, ai_env):
    """AI can suggest eat_out and skip day types."""
    plan = client.get("/api/plans/current").json()
    suggestions = [
        {"day_of_week": 0, "day_type": "home_cooked", "meal_id": meals[0]["id"],
         "meal_name": meals[0]["name"], "custom_name": "", "notes": ""},
        {"day_of_week": 1, "day_type": "eat_out", "meal_id": None,
         "meal_name": "", "custom_name": "Pizza Place", "notes": ""},
        {"day_of_week": 2, "day_type": "skip", "meal_id": None,
         "meal_name": "", "custom_name": "Leftovers", "notes": ""},
        {"day_of_week": 3, "day_type": "home_cooked", "meal_id": meals[1]["id"],
         "meal_name": meals[1]["name"], "custom_name": "", "notes": ""},
        {"day_of_week": 4, "day_type": "home_cooked", "meal_id": meals[2]["id"],
         "meal_name": meals[2]["name"], "custom_name": "", "notes": ""},
        {"day_of_week": 5, "day_type": "eat_out", "meal_id": None,
         "meal_name": "", "custom_name": "Sushi", "notes": ""},
        {"day_of_week": 6, "day_type": "home_cooked", "meal_id": meals[0]["id"],
         "meal_name": meals[0]["name"], "custom_name": "", "notes": ""},
    ]

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    result = {s["day_of_week"]: s for s in r.json()["suggestions"]}
    assert result[1]["day_type"] == "eat_out"
    assert result[1]["custom_name"] == "Pizza Place"
    assert result[2]["day_type"] == "skip"


def test_generate_invalid_day_type_defaults_to_skip(client, meals, ai_env):
    """AI returning an invalid day_type should default to skip."""
    plan = client.get("/api/plans/current").json()
    suggestions = [
        {"day_of_week": i, "day_type": "invalid_type" if i == 0 else "home_cooked",
         "meal_id": meals[0]["id"], "meal_name": meals[0]["name"],
         "custom_name": "", "notes": ""}
        for i in range(7)
    ]

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": plan["week_start"],
                "existing_plan_id": plan["id"],
            })

    assert r.status_code == 200
    result = {s["day_of_week"]: s for s in r.json()["suggestions"]}
    assert result[0]["day_type"] == "skip"


def test_generate_with_history_and_week_notes(client, meals, ai_env):
    """Generate with a prior plan (meals assigned) and current plan notes covers history+context paths."""
    from datetime import timedelta

    current_plan = client.get("/api/plans/current").json()
    current_week = date.fromisoformat(current_plan["week_start"])

    # Create a PAST week plan with meals and custom names → history
    past_week = (current_week - timedelta(weeks=1)).isoformat()
    past_plan = client.get(f"/api/plans/week/{past_week}").json()
    client.put(f"/api/plans/{past_plan['id']}/days/0", json={
        "day_type": "home_cooked", "meal_id": meals[0]["id"],
    })
    client.put(f"/api/plans/{past_plan['id']}/days/1", json={
        "day_type": "eat_out", "custom_name": "Pizza Hut",
    })

    # Add plan-level notes to CURRENT plan → week_context
    client.put(f"/api/plans/{current_plan['id']}/notes", json={
        "notes": "Guests visiting this week",
    })

    # Generate for the current week (past plan is history, current has notes)
    suggestions = _mock_suggestions(meals)

    with patch("app.routers.ai._call_anthropic", return_value=suggestions):
        with ai_env:
            r = client.post("/api/ai/generate", json={
                "week_start": current_plan["week_start"],
                "existing_plan_id": current_plan["id"],
            })

    assert r.status_code == 200
    assert len(r.json()["suggestions"]) == 7


# ── Config env vars ───────────────────────────────────────────────────────────

def test_ai_model_anthropic_env_override():
    """AI_MODEL_ANTHROPIC env var is forwarded to the Anthropic messages.create call."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_anthropic

    mock_instance = MagicMock()
    mock_instance.messages.create.return_value = MagicMock(
        content=[MagicMock(text='[{"day_of_week": 0}]')]
    )

    with patch("anthropic.Anthropic", return_value=mock_instance):
        with patch.dict(os.environ, {"AI_MODEL_ANTHROPIC": "claude-opus-4-6"}):
            _call_anthropic("test prompt", "sk-test")

    call_kwargs = mock_instance.messages.create.call_args
    assert call_kwargs.kwargs["model"] == "claude-opus-4-6"


def test_call_openai_compatible_forwards_base_url_and_model():
    """base_url is passed to the OpenAI client and AI_MODEL_OPENAI_COMPATIBLE is forwarded."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='[{"day_of_week": 0}]'))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance) as mock_client:
        with patch.dict(os.environ, {"AI_MODEL_OPENAI_COMPATIBLE": "local-llama"}):
            result = _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")

    assert result == [{"day_of_week": 0}]
    mock_client.assert_called_once()
    assert mock_client.call_args.kwargs["base_url"] == "https://litellm.home/v1"
    assert mock_client.call_args.kwargs["api_key"] == "sk-test"
    assert mock_instance.chat.completions.create.call_args.kwargs["model"] == "local-llama"


def test_call_openai_compatible_default_max_tokens():
    """Defaults to a higher max_tokens than the other providers, to leave room for
    reasoning models that spend part of the budget on hidden reasoning tokens."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='[{"day_of_week": 0}]'))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        with patch.dict(os.environ, {}, clear=True):
            _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")

    assert mock_instance.chat.completions.create.call_args.kwargs["max_tokens"] == 4096


def test_call_openai_compatible_max_tokens_env_override():
    """AI_MAX_TOKENS_OPENAI_COMPATIBLE overrides the default max_tokens."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='[{"day_of_week": 0}]'))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        with patch.dict(os.environ, {"AI_MAX_TOKENS_OPENAI_COMPATIBLE": "8000"}):
            _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")

    assert mock_instance.chat.completions.create.call_args.kwargs["max_tokens"] == 8000


def test_call_openai_compatible_empty_content_raises_clear_error():
    """A reasoning model that burns its whole token budget on hidden reasoning returns
    empty content — this should raise a clear, actionable error, not a bare JSON error."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        try:
            _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "empty response" in str(exc).lower()
            assert "AI_MAX_TOKENS_OPENAI_COMPATIBLE" in str(exc)


def test_call_openai_compatible_none_content_raises_clear_error():
    """message.content can be None (not just empty string) — must not crash on .strip()."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=None))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        try:
            _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "empty response" in str(exc).lower()


def test_call_openai_compatible_allow_reasoning_drops_max_tokens():
    """AI_ALLOW_REASONING_OPENAI_COMPATIBLE=true omits max_tokens from the request entirely,
    even if AI_MAX_TOKENS_OPENAI_COMPATIBLE is also set — reasoning takes precedence."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='[{"day_of_week": 0}]'))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        with patch.dict(os.environ, {
            "AI_ALLOW_REASONING_OPENAI_COMPATIBLE": "true",
            "AI_MAX_TOKENS_OPENAI_COMPATIBLE": "8000",
        }):
            result = _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")

    assert result == [{"day_of_week": 0}]
    assert "max_tokens" not in mock_instance.chat.completions.create.call_args.kwargs


def test_call_openai_compatible_allow_reasoning_empty_content_still_raises():
    """Even with the cap removed, an empty response should still raise a clear error,
    not crash — the message just shouldn't blame max_tokens this time."""
    from unittest.mock import MagicMock
    from app.routers.ai import _call_openai_compatible

    mock_instance = MagicMock()
    mock_instance.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))]
    )

    with patch("app.routers.ai.OpenAI", return_value=mock_instance):
        with patch.dict(os.environ, {"AI_ALLOW_REASONING_OPENAI_COMPATIBLE": "true"}):
            try:
                _call_openai_compatible("test prompt", "sk-test", "https://litellm.home/v1")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "empty response" in str(exc).lower()
