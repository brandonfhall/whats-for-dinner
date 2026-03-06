import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProteinInventory
from app.schemas import (
    ProteinInventoryCreate,
    ProteinInventoryOut,
    ProteinInventoryUpdate,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


@router.get("/proteins", response_model=list[ProteinInventoryOut])
def list_proteins(db: Session = Depends(get_db)):
    return db.query(ProteinInventory).order_by(ProteinInventory.protein_name).all()


@router.post("/proteins", response_model=ProteinInventoryOut, status_code=201)
def create_protein(payload: ProteinInventoryCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(ProteinInventory)
        .filter(ProteinInventory.protein_name == payload.protein_name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Protein already exists")
    data = payload.model_dump()
    data["quantity"] = max(0, data.get("quantity", 0))
    entry = ProteinInventory(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info("Protein created | %s", entry.protein_name)
    return entry


@router.put("/proteins/{protein_name}", response_model=ProteinInventoryOut)
def update_protein(
    protein_name: str,
    payload: ProteinInventoryUpdate,
    db: Session = Depends(get_db),
):
    entry = (
        db.query(ProteinInventory)
        .filter(ProteinInventory.protein_name == protein_name)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Protein not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "quantity" and value is not None:
            value = max(0, value)
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    logger.info("Protein updated | %s", entry.protein_name)
    return entry


@router.patch("/proteins/{protein_name}/adjust", response_model=ProteinInventoryOut)
def adjust_protein(
    protein_name: str,
    delta: float,
    db: Session = Depends(get_db),
):
    """Increment or decrement protein quantity by delta."""
    entry = (
        db.query(ProteinInventory)
        .filter(ProteinInventory.protein_name == protein_name)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Protein not found")
    entry.quantity = max(0, entry.quantity + delta)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/proteins/{protein_name}", status_code=204)
def delete_protein(protein_name: str, db: Session = Depends(get_db)):
    entry = (
        db.query(ProteinInventory)
        .filter(ProteinInventory.protein_name == protein_name)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Protein not found")
    db.delete(entry)
    db.commit()
    logger.info("Protein deleted | %s", protein_name)
