import json
import os
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import WeeklyPlan, PlanDay, Meal, DayType, PlanStatus
from app.schemas import AIGenerateRequest, AIGenerateResponse, AIDaySuggestion
from app.routers.settings import get_all_settings

router = APIRouter(prefix="/api/ai", tags=["ai"])

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _check_configured(provider: str) -> tuple[bool, str | None]:
    """Return (is_configured, reason_if_not)."""
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return False, "OPENAI_API_KEY is not set in your .env file."
    else:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return False, "ANTHROPIC_API_KEY is not set in your .env file."
    return True, None


@router.get("/status")
def ai_status(db: Session = Depends(get_db)):
    settings = get_all_settings(db)
    provider = os.getenv("AI_PROVIDER", settings.get("ai_provider", "anthropic"))
    configured, reason = _check_configured(provider)
    return {"configured": configured, "provider": provider, "reason": reason}


def _get_meal_library(db: Session) -> list[dict]:
    meals = db.query(Meal).filter(Meal.active == True).all()  # noqa: E712
    return [
        {
            "id": m.id,
            "name": m.name,
            "type": m.meal_type.value,
            "notes": m.notes,
            "has_leftovers": m.has_leftovers,
            "easy_to_make": m.easy_to_make,
            "shared_ingredients": m.shared_ingredients,
            "protein": m.protein,
        }
        for m in meals
    ]


def _get_history(db: Session, before: date, weeks: int = 8) -> list[dict]:
    cutoff = before - timedelta(weeks=weeks)
    plans = (
        db.query(WeeklyPlan)
        .options(joinedload(WeeklyPlan.days).joinedload(PlanDay.meal))
        .filter(WeeklyPlan.week_start >= cutoff, WeeklyPlan.week_start < before)
        .order_by(WeeklyPlan.week_start.desc())
        .all()
    )
    history = []
    for plan in plans:
        week = {"week_start": plan.week_start.isoformat(), "days": []}
        for day in sorted(plan.days, key=lambda d: d.day_of_week):
            entry = {
                "day": DAY_NAMES[day.day_of_week],
                "type": day.day_type.value,
            }
            if day.meal:
                entry["meal"] = day.meal.name
            elif day.custom_name:
                entry["meal"] = day.custom_name
            week["days"].append(entry)
        history.append(week)
    return history


def _build_prompt(
    week_start: date,
    library: list[dict],
    history: list[dict],
    gym_days: list[int],
    eat_out_days: list[int],
) -> str:
    gym_names = [DAY_NAMES[d] for d in gym_days]
    eat_out_names = [DAY_NAMES[d] for d in eat_out_days]

    prompt = f"""You are helping plan dinners for a household for the week of {week_start.strftime('%B %d, %Y')}.

MEAL LIBRARY (meals they know and like):
{json.dumps(library, indent=2)}

RECENT HISTORY (last 8 weeks of dinners):
{json.dumps(history, indent=2)}

CONSTRAINTS FOR THIS WEEK:
- Gym nights (prefer easy_to_make meals): {gym_names if gym_names else 'none'}
- Eat-out nights (set day_type to eat_out, no meal_id needed): {eat_out_names if eat_out_names else 'none'}

INSTRUCTIONS:
1. Suggest a dinner for all 7 nights (Monday through Sunday, days 0-6).
2. For eat-out nights, set day_type to "eat_out" and provide a custom_name like "Pizza place" or "Mexican" — leave meal_id null.
3. For gym nights, strongly prefer meals where easy_to_make is true. Set day_type to "home_cooked".
4. For all other nights, pick from the meal library. Vary choices — avoid repeating meals used in the last 2 weeks if possible.
5. Try to vary the protein across the week — avoid scheduling the same protein on back-to-back nights when alternatives exist.
6. When two consecutive home-cooked nights share ingredients, note it in the notes field.
7. If a meal has has_leftovers=true, you may note that in the next day's notes.

Respond with ONLY a valid JSON array (no markdown, no explanation) with exactly 7 objects in this format:
[
  {{
    "day_of_week": 0,
    "day_type": "home_cooked",
    "meal_id": 1,
    "meal_name": "Chicken Stir Fry",
    "custom_name": "",
    "notes": ""
  }},
  ...
]
"""
    return prompt


def _call_anthropic(prompt: str) -> list[dict]:
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY is not set in your .env file.")
    client = anthropic.Anthropic(api_key=key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        system="You are a helpful meal planner. Respond with valid JSON only — no markdown fences, no extra text.",
    )
    raw = message.content[0].text.strip()
    return json.loads(raw)


def _call_openai(prompt: str) -> list[dict]:
    from openai import OpenAI
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY is not set in your .env file.")
    client = OpenAI(api_key=key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful meal planner. Respond with valid JSON only — no markdown fences, no extra text.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
        response_format={"type": "json_object"},
    )
    # gpt-4o json_object mode wraps in an object, handle both cases
    raw = response.choices[0].message.content.strip()
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return parsed
    # if wrapped in an object, look for the array
    for v in parsed.values():
        if isinstance(v, list):
            return v
    raise ValueError("Unexpected OpenAI response shape")


def _apply_suggestions(
    plan_id: int,
    suggestions: list[dict],
    db: Session,
    meal_ids: set[int],
) -> list[AIDaySuggestion]:
    result = []
    for s in suggestions:
        dow = int(s.get("day_of_week", 0))
        day_type_raw = s.get("day_type", "skip")
        try:
            day_type = DayType(day_type_raw)
        except ValueError:
            day_type = DayType.skip

        meal_id = s.get("meal_id")
        if meal_id and int(meal_id) not in meal_ids:
            meal_id = None  # AI hallucinated an ID

        day = db.query(PlanDay).filter(
            PlanDay.plan_id == plan_id, PlanDay.day_of_week == dow
        ).first()
        if not day:
            day = PlanDay(plan_id=plan_id, day_of_week=dow)
            db.add(day)

        day.day_type = day_type
        day.meal_id = int(meal_id) if meal_id and day_type == DayType.home_cooked else None
        day.custom_name = s.get("custom_name", "") or ""
        day.notes = s.get("notes", "") or ""

        result.append(
            AIDaySuggestion(
                day_of_week=dow,
                day_type=day_type,
                meal_id=day.meal_id,
                meal_name=s.get("meal_name", "") or "",
                custom_name=day.custom_name,
                notes=day.notes,
            )
        )
    return result


@router.post("/generate", response_model=AIGenerateResponse)
def generate_plan(payload: AIGenerateRequest, db: Session = Depends(get_db)):
    settings = get_all_settings(db)
    provider = os.getenv("AI_PROVIDER", settings.get("ai_provider", "anthropic"))

    library = _get_meal_library(db)
    if not library:
        raise HTTPException(
            status_code=400,
            detail="Add some meals to your library before generating a plan.",
        )

    history = _get_history(db, payload.week_start)
    prompt = _build_prompt(
        payload.week_start, library, history, settings["gym_days"], settings["eat_out_days"]
    )

    configured, reason = _check_configured(provider)
    if not configured:
        raise HTTPException(status_code=503, detail=reason)

    try:
        if provider == "openai":
            raw_suggestions = _call_openai(prompt)
        else:
            raw_suggestions = _call_anthropic(prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"AI request failed: {exc}") from exc

    # get or create the plan
    from app.routers.plans import _monday_of, _build_plan_days, _load_plan

    week_start = _monday_of(payload.week_start)
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.week_start == week_start).first()
    if payload.existing_plan_id:
        plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == payload.existing_plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
    if not plan:
        plan = WeeklyPlan(week_start=week_start, status=PlanStatus.draft, ai_generated=True)
        db.add(plan)
        db.flush()
        days = _build_plan_days(plan.id, settings["gym_days"], settings["eat_out_days"])
        db.add_all(days)
        db.flush()

    plan.ai_generated = True
    valid_meal_ids = {m["id"] for m in library}
    suggestions = _apply_suggestions(plan.id, raw_suggestions, db, valid_meal_ids)
    db.commit()

    return AIGenerateResponse(suggestions=suggestions, plan_id=plan.id)
