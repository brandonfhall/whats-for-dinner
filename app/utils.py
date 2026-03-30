"""Shared helpers used across multiple routers."""
from datetime import date, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session

DAY_NAMES = [
    "Sunday", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday",
]


def get_or_404(db: Session, model, detail: str = "Not found", **filters):
    """Query for a single row by the given filters; raise 404 if missing."""
    q = db.query(model)
    for attr, value in filters.items():
        q = q.filter(getattr(model, attr) == value)
    obj = q.first()
    if not obj:
        raise HTTPException(status_code=404, detail=detail)
    return obj


def sunday_of(d: date) -> date:
    """Return the Sunday that starts the week containing *d*."""
    return d - timedelta(days=(d.weekday() + 1) % 7)
