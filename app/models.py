from datetime import datetime, date, timezone
from sqlalchemy import (
    Integer, String, Boolean, Date, DateTime, Float, ForeignKey, Enum as SAEnum,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class MealType(str, enum.Enum):
    home_cooked = "home_cooked"
    eat_out = "eat_out"
    other = "other"
    frozen = "frozen"


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
    protein: Mapped[str] = mapped_column(String, default="")
    cuisine: Mapped[str] = mapped_column(String, default="")
    frozen_quantity: Mapped[int] = mapped_column(Integer, default=0)
    protein_servings: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("frozen_quantity >= 0", name="ck_meals_frozen_quantity_nonneg"),
        CheckConstraint("protein_servings >= 0", name="ck_meals_protein_servings_nonneg"),
    )

    plan_days: Mapped[list["PlanDay"]] = relationship("PlanDay", back_populates="meal")


class WeeklyPlan(Base):
    __tablename__ = "weekly_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    status: Mapped[PlanStatus] = mapped_column(SAEnum(PlanStatus), default=PlanStatus.draft)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    days: Mapped[list["PlanDay"]] = relationship(
        "PlanDay", back_populates="plan", order_by="PlanDay.day_of_week"
    )


class PlanDay(Base):
    __tablename__ = "plan_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("weekly_plans.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Sun … 6=Sat
    day_type: Mapped[DayType] = mapped_column(SAEnum(DayType), default=DayType.skip)
    meal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("meals.id"), nullable=True)
    custom_name: Mapped[str] = mapped_column(String, default="")  # for eat_out nights
    notes: Mapped[str] = mapped_column(String, default="")
    carry_forward: Mapped[bool] = mapped_column(Boolean, default=False)

    plan: Mapped["WeeklyPlan"] = relationship("WeeklyPlan", back_populates="days")
    meal: Mapped["Meal | None"] = relationship("Meal", back_populates="plan_days")


class ProteinInventory(Base):
    __tablename__ = "protein_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    protein_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    emoji: Mapped[str] = mapped_column(String, default="")
    group: Mapped[str] = mapped_column(String, default="meat")
    quantity: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[str] = mapped_column(String, default="servings")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_protein_inventory_quantity_nonneg"),
    )


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)  # JSON-encoded
