import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Setting
from app.schemas import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

DEFAULTS = {
    "gym_days": [],
    "eat_out_days": [],
    "ai_provider": "anthropic",
}


def get_all_settings(db: Session) -> dict:
    rows = db.query(Setting).all()
    result = dict(DEFAULTS)
    for row in rows:
        result[row.key] = json.loads(row.value)
    return result


def set_setting(db: Session, key: str, value) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = json.dumps(value)
    else:
        db.add(Setting(key=key, value=json.dumps(value)))
    db.commit()


@router.get("", response_model=SettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.put("", response_model=SettingsOut)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        set_setting(db, key, value)
    return get_all_settings(db)
