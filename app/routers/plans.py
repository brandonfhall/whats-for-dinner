import logging
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import WeeklyPlan, PlanDay, DayType, PlanStatus, Meal, MealType, ProteinInventory
from app.schemas import (
    WeeklyPlanCreate, WeeklyPlanOut, WeeklyPlanSummary, WeeklyPlanNotesUpdate,
    PlanDayUpdate, PlanDayOut, ShoppingListOut, ShoppingListItem,
)
from app.routers.settings import get_all_settings

router = APIRouter(prefix="/api/plans", tags=["plans"])
logger = logging.getLogger(__name__)

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _sunday_of(d: date) -> date:
    """Return the Sunday that starts the week containing d."""
    return d - timedelta(days=(d.weekday() + 1) % 7)


def _build_plan_days(plan_id: int, gym_days: list[int], eat_out_days: list[int]) -> list[PlanDay]:
    days = []
    for dow in range(7):
        if dow in eat_out_days:
            day_type = DayType.eat_out
        elif dow in gym_days:
            day_type = DayType.home_cooked  # gym night — still home, AI will prefer easy meals
        else:
            day_type = DayType.skip
        days.append(PlanDay(plan_id=plan_id, day_of_week=dow, day_type=day_type))
    return days


def _apply_carry_forward(days: list[PlanDay], sunday: date, db: Session) -> None:
    """For any skip day in `days`, copy assignment from previous week if carry_forward=True."""
    prev_sunday = sunday - timedelta(weeks=1)
    prev_plan = db.query(WeeklyPlan).filter(WeeklyPlan.week_start == prev_sunday).first()
    if not prev_plan:
        return
    carry = {
        d.day_of_week: d
        for d in db.query(PlanDay).filter(
            PlanDay.plan_id == prev_plan.id, PlanDay.carry_forward == True  # noqa: E712
        ).all()
    }
    for day in days:
        src = carry.get(day.day_of_week)
        if not src:
            continue
        # A day is "unfilled" if it hasn't been explicitly planned yet —
        # skip, eat_out with no custom name, or home_cooked with no meal
        # (the last two are just defaults from settings, not real choices).
        unfilled = (
            day.day_type == DayType.skip
            or (day.day_type == DayType.eat_out and not day.custom_name)
            or (day.day_type == DayType.home_cooked and not day.meal_id)
        )
        if unfilled:
            day.day_type = src.day_type
            day.meal_id = src.meal_id
            day.custom_name = src.custom_name
            day.carry_forward = True


def _get_or_create_plan(sunday: date, db: Session) -> WeeklyPlan:
    """Return existing plan for the week, or create one (with carry-forward applied)."""
    plan = (
        db.query(WeeklyPlan)
        .options(joinedload(WeeklyPlan.days).joinedload(PlanDay.meal))
        .filter(WeeklyPlan.week_start == sunday)
        .first()
    )
    if plan:
        return plan
    settings = get_all_settings(db)
    plan = WeeklyPlan(week_start=sunday, status=PlanStatus.draft)
    db.add(plan)
    db.flush()
    days = _build_plan_days(plan.id, settings["gym_days"], settings["eat_out_days"])
    _apply_carry_forward(days, sunday, db)
    db.add_all(days)
    db.commit()
    logger.info("Plan created | week=%s", sunday.isoformat())
    return _load_plan(plan.id, db)


def _load_plan(plan_id: int, db: Session) -> WeeklyPlan:
    plan = (
        db.query(WeeklyPlan)
        .options(joinedload(WeeklyPlan.days).joinedload(PlanDay.meal))
        .filter(WeeklyPlan.id == plan_id)
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.get("", response_model=list[WeeklyPlanSummary])
def list_plans(db: Session = Depends(get_db)):
    return db.query(WeeklyPlan).order_by(WeeklyPlan.week_start.desc()).all()


@router.get("/current", response_model=WeeklyPlanOut)
def get_or_create_current_plan(db: Session = Depends(get_db)):
    return _get_or_create_plan(_sunday_of(date.today()), db)


@router.get("/week/{week_start}", response_model=WeeklyPlanOut)
def get_or_create_plan_for_week(week_start: date, db: Session = Depends(get_db)):
    return _get_or_create_plan(_sunday_of(week_start), db)


@router.post("", response_model=WeeklyPlanOut, status_code=201)
def create_plan(payload: WeeklyPlanCreate, db: Session = Depends(get_db)):
    week_start = _sunday_of(payload.week_start)
    if db.query(WeeklyPlan).filter(WeeklyPlan.week_start == week_start).first():
        raise HTTPException(status_code=409, detail="A plan for that week already exists")
    return _get_or_create_plan(week_start, db)


@router.get("/{plan_id}", response_model=WeeklyPlanOut)
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    return _load_plan(plan_id, db)


@router.put("/{plan_id}/days/{dow}", response_model=PlanDayOut)
def update_day(plan_id: int, dow: int, payload: PlanDayUpdate, db: Session = Depends(get_db)):
    if dow < 0 or dow > 6:
        raise HTTPException(status_code=422, detail="day_of_week must be 0-6")
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    day = db.query(PlanDay).filter(PlanDay.plan_id == plan_id, PlanDay.day_of_week == dow).first()
    if not day:
        day = PlanDay(plan_id=plan_id, day_of_week=dow)
        db.add(day)

    day.day_type = payload.day_type
    day.meal_id = payload.meal_id if payload.day_type == DayType.home_cooked else None
    day.custom_name = payload.custom_name
    day.notes = payload.notes
    day.carry_forward = payload.carry_forward
    db.commit()
    db.refresh(day)
    if day.meal_id:
        day = db.query(PlanDay).options(joinedload(PlanDay.meal)).filter(PlanDay.id == day.id).first()
    detail = (day.meal.name if day.meal else day.custom_name) or day.day_type.value
    logger.info("Plan day updated | plan=%d %s → %s (%s)", plan_id, DAY_NAMES[dow], detail, day.day_type.value)
    return day


@router.put("/{plan_id}/notes", response_model=WeeklyPlanSummary)
def update_plan_notes(plan_id: int, payload: WeeklyPlanNotesUpdate, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.notes = payload.notes
    db.commit()
    db.refresh(plan)
    return plan


@router.put("/{plan_id}/status", response_model=WeeklyPlanSummary)
def update_plan_status(plan_id: int, status: PlanStatus, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = status
    db.commit()
    db.refresh(plan)
    logger.info("Plan status changed | plan=%d → %s", plan_id, status.value)
    return plan


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(WeeklyPlan).filter(WeeklyPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.query(PlanDay).filter(PlanDay.plan_id == plan_id).delete()
    db.delete(plan)
    db.commit()


@router.get("/{plan_id}/shopping-list", response_model=ShoppingListOut)
def get_shopping_list(plan_id: int, db: Session = Depends(get_db)):
    plan = _load_plan(plan_id, db)
    protein_needs: dict[str, float] = {}
    frozen_needs: dict[int, int] = {}

    for day in plan.days:
        if day.day_type != DayType.home_cooked or not day.meal:
            continue
        meal = day.meal
        if meal.meal_type == MealType.frozen:
            frozen_needs[meal.id] = frozen_needs.get(meal.id, 0) + 1
        if meal.protein:
            protein_needs[meal.protein] = (
                protein_needs.get(meal.protein, 0) + meal.protein_servings
            )

    items: list[ShoppingListItem] = []

    # Protein shortages
    if protein_needs:
        inv_rows = (
            db.query(ProteinInventory)
            .filter(ProteinInventory.protein_name.in_(protein_needs.keys()))
            .all()
        )
        inv_map = {r.protein_name: r for r in inv_rows}
        for protein_name, needed in sorted(protein_needs.items()):
            inv = inv_map.get(protein_name)
            on_hand = inv.quantity if inv else 0
            unit = inv.unit if inv else "servings"
            items.append(ShoppingListItem(
                item_name=protein_name,
                item_type="protein",
                needed=needed,
                on_hand=on_hand,
                shortage=max(0, needed - on_hand),
                unit=unit,
            ))

    # Frozen meal shortages
    if frozen_needs:
        frozen_meals = (
            db.query(Meal).filter(Meal.id.in_(frozen_needs.keys())).all()
        )
        for meal in sorted(frozen_meals, key=lambda m: m.name):
            needed = frozen_needs[meal.id]
            items.append(ShoppingListItem(
                item_name=meal.name,
                item_type="frozen",
                needed=needed,
                on_hand=meal.frozen_quantity,
                shortage=max(0, needed - meal.frozen_quantity),
                unit="portions",
            ))

    return ShoppingListOut(week_start=plan.week_start, items=items)
