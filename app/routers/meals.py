from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Meal
from app.schemas import MealCreate, MealOut, MealUpdate

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.get("", response_model=list[MealOut])
def list_meals(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Meal)
    if active_only:
        q = q.filter(Meal.active == True)  # noqa: E712
    return q.order_by(Meal.name).all()


@router.post("", response_model=MealOut, status_code=201)
def create_meal(payload: MealCreate, db: Session = Depends(get_db)):
    meal = Meal(**payload.model_dump())
    db.add(meal)
    db.commit()
    db.refresh(meal)
    return meal


@router.get("/{meal_id}", response_model=MealOut)
def get_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    return meal


@router.put("/{meal_id}", response_model=MealOut)
def update_meal(meal_id: int, payload: MealUpdate, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(meal, field, value)
    db.commit()
    db.refresh(meal)
    return meal


@router.delete("/{meal_id}", status_code=204)
def delete_meal(meal_id: int, db: Session = Depends(get_db)):
    meal = db.query(Meal).filter(Meal.id == meal_id).first()
    if not meal:
        raise HTTPException(status_code=404, detail="Meal not found")
    meal.active = False
    db.commit()
