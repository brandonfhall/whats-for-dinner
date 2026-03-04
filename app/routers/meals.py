import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meal, PlanDay
from app.schemas import MealCreate, MealOut, MealUpdate

router = APIRouter(prefix="/api/meals", tags=["meals"])
logger = logging.getLogger(__name__)


def _usage_counts(db: Session) -> dict[int, int]:
    """Return a map of meal_id → number of times it has appeared in any plan day."""
    rows = (
        db.query(PlanDay.meal_id, func.count(PlanDay.id).label("cnt"))
        .filter(PlanDay.meal_id.is_not(None))
        .group_by(PlanDay.meal_id)
        .all()
    )
    return {row.meal_id: row.cnt for row in rows}


def _with_usage(meal: Meal, counts: dict[int, int]) -> MealOut:
    out = MealOut.model_validate(meal)
    out.times_used = counts.get(meal.id, 0)
    return out


@router.get("", response_model=list[MealOut])
def list_meals(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Meal)
    if active_only:
        q = q.filter(Meal.active == True)  # noqa: E712
    meals = q.order_by(Meal.name).all()
    counts = _usage_counts(db)
    return [_with_usage(m, counts) for m in meals]


@router.post("", response_model=MealOut, status_code=201)
def create_meal(payload: MealCreate, db: Session = Depends(get_db)):
    meal = Meal(**payload.model_dump())
    db.add(meal)
    db.commit()
    db.refresh(meal)
    logger.info("Meal created | %r (%s)", meal.name, meal.meal_type.value)
    return meal


@router.get("/{meal_id}", response_model=MealOut)
def get_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    counts = _usage_counts(db)
    return _with_usage(meal, counts)


@router.put("/{meal_id}", response_model=MealOut)
def update_meal(meal_id: int, payload: MealUpdate, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(meal, field, value)
    db.commit()
    db.refresh(meal)
    logger.info("Meal updated | %r", meal.name)
    return meal


@router.delete("/{meal_id}", status_code=204)
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    logger.info("Meal deactivated | %r", meal.name)
    meal.active = False
    db.commit()
