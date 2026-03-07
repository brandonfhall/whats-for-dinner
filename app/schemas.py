from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel

from app.models import MealType, DayType, PlanStatus


# ── Meals ────────────────────────────────────────────────────────────────────

class MealBase(BaseModel):
    name: str
    meal_type: MealType = MealType.home_cooked
    notes: str = ""
    recipe_url: str = ""
    has_leftovers: bool = False
    easy_to_make: bool = False
    shared_ingredients: str = ""
    protein: str = ""  # e.g. "Chicken", "Beef", "Tofu" — selected from protein_inventory
    cuisine: str = ""  # e.g. "Italian", "Mexican" — selected from a preset list
    frozen_quantity: int = 0
    protein_servings: int = 1


class MealCreate(MealBase):
    pass


class MealUpdate(MealBase):
    name: Optional[str] = None
    meal_type: Optional[MealType] = None
    active: Optional[bool] = None
    frozen_quantity: Optional[int] = None
    protein_servings: Optional[int] = None


class MealOut(MealBase):
    id: int
    active: bool
    created_at: datetime
    times_used: int = 0

    model_config = {"from_attributes": True}


# ── Plan Days ─────────────────────────────────────────────────────────────────

class PlanDayUpdate(BaseModel):
    day_type: DayType
    meal_id: Optional[int] = None
    custom_name: str = ""
    notes: str = ""
    carry_forward: bool = False


class PlanDayOut(BaseModel):
    id: int
    day_of_week: int
    day_type: DayType
    meal_id: Optional[int]
    custom_name: str
    notes: str
    carry_forward: bool = False
    meal: Optional[MealOut] = None

    model_config = {"from_attributes": True}


# ── Weekly Plans ──────────────────────────────────────────────────────────────

class WeeklyPlanCreate(BaseModel):
    week_start: date  # must be a Sunday


class WeeklyPlanOut(BaseModel):
    id: int
    week_start: date
    status: PlanStatus
    ai_generated: bool
    notes: str = ""
    created_at: datetime
    days: list[PlanDayOut] = []

    model_config = {"from_attributes": True}


class WeeklyPlanSummary(BaseModel):
    id: int
    week_start: date
    status: PlanStatus
    ai_generated: bool
    notes: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class WeeklyPlanNotesUpdate(BaseModel):
    notes: str


# ── AI ────────────────────────────────────────────────────────────────────────

class AIGenerateRequest(BaseModel):
    week_start: date
    existing_plan_id: Optional[int] = None
    mode: str = "mix"  # "mix" = favour less-used meals, "safe" = favour favourites


class AIDaySuggestion(BaseModel):
    day_of_week: int  # 0-6
    day_type: DayType
    meal_id: Optional[int] = None
    meal_name: str = ""
    custom_name: str = ""
    notes: str = ""


class AIGenerateResponse(BaseModel):
    suggestions: list[AIDaySuggestion]
    plan_id: int  # the plan that was created/updated


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsOut(BaseModel):
    gym_days: list[int] = []          # 0=Mon … 6=Sun
    eat_out_days: list[int] = []
    ai_provider: str = "anthropic"


class SettingsUpdate(BaseModel):
    gym_days: Optional[list[int]] = None
    eat_out_days: Optional[list[int]] = None
    ai_provider: Optional[str] = None


# ── Protein Inventory ────────────────────────────────────────────────────────

class ProteinInventoryCreate(BaseModel):
    protein_name: str
    display_name: str
    emoji: str = ""
    group: str = "meat"
    quantity: float = 0
    unit: str = "servings"


class ProteinInventoryUpdate(BaseModel):
    display_name: Optional[str] = None
    emoji: Optional[str] = None
    group: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None


class ProteinInventoryOut(BaseModel):
    id: int
    protein_name: str
    display_name: str
    emoji: str
    group: str
    quantity: float
    unit: str

    model_config = {"from_attributes": True}


# ── Shopping List ────────────────────────────────────────────────────────────

class ShoppingListItem(BaseModel):
    item_name: str
    item_type: str       # "protein" or "frozen"
    needed: float
    on_hand: float
    shortage: float
    unit: str = ""


class ShoppingListOut(BaseModel):
    week_start: date
    items: list[ShoppingListItem] = []
