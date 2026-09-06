import json
import logging
import os

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

DEFAULTS = {
    "gym_days": [],
    "eat_out_days": [],
    "ai_provider": "anthropic",
    "ai_api_key": "",
    "ai_base_url": "",
    "ai_model_anthropic": "",
    "ai_model_openai": "",
    "ai_model_openai_compatible": "",
    "custom_instructions": "",
}


def get_all_settings(db: Session) -> dict:
    rows = db.query(Setting).all()
    result = dict(DEFAULTS)
    for row in rows:
        try:
            result[row.key] = json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass  # skip corrupt values, keep Pydantic defaults
    return result


def set_setting(db: Session, key: str, value) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = json.dumps(value)
    else:
        db.add(Setting(key=key, value=json.dumps(value)))
    db.commit()


def _annotate_key_configured(data: dict) -> dict:
    """Add ai_key_configured to a settings dict; strip the raw key before returning."""
    data["ai_key_configured"] = bool(os.getenv("AI_API_KEY") or data.get("ai_api_key", ""))
    data.pop("ai_api_key", None)
    return data


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return _annotate_key_configured(get_all_settings(db))


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        set_setting(db, key, value)
    logger.info("Settings updated | %s", ", ".join(
        f"{k}=***" if k == "ai_api_key" else f"{k}={v}" for k, v in updates.items()
    ))
    return _annotate_key_configured(get_all_settings(db))
