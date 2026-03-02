from datetime import datetime, date
from sqlalchemy import (
    Integer, String, Boolean, Date, DateTime, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class MealType(str, enum.Enum):
    home_cooked = "home_cooked"
    eat_out = "eat_out"
    other = "other"


class DayType(str, enum.Enum):
    home_cooked = "home_cooked"
    eat_out = "eat_out"
    skip = "skip"


class PlanStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    complete = "complete"


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    meal_type: Mapped[MealType] = mapped_column(SAEnum(MealType), default=MealType.home_cooked)
    notes: Mapped[str] = mapped_column(String, default="")
    recipe_url: Mapped[str] = mapped_column(String, default="")
    has_leftovers: Mapped[bool] = mapped_column(Boolean, default=False)
    easy_to_make: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_ingredients: Mapped[str] = mapped_column(String, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    plan_days: Mapped[list["PlanDay"]] = relationship("PlanDay", back_populates="meal")


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    status: Mapped[PlanStatus] = mapped_column(SAEnum(PlanStatus), default=PlanStatus.draft)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    days: Mapped[list["PlanDay"]] = relationship(
        "PlanDay", back_populates="plan", order_by="PlanDay.day_of_week"
    )


class PlanDay(Base):
    __tablename__ = "plan_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("weekly_plans.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon … 6=Sun
    day_type: Mapped[DayType] = mapped_column(SAEnum(DayType), default=DayType.skip)
    meal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("meals.id"), nullable=True)
    custom_name: Mapped[str] = mapped_column(String, default="")  # for eat_out nights
    notes: Mapped[str] = mapped_column(String, default="")

    plan: Mapped["WeeklyPlan"] = relationship("WeeklyPlan", back_populates="days")
    meal: Mapped["Meal | None"] = relationship("Meal", back_populates="plan_days")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)  # JSON-encoded
