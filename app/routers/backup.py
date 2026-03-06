import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.database import backup_db, BACKUP_DIR

router = APIRouter(prefix="/api/backup", tags=["backup"])
logger = logging.getLogger(__name__)


@router.post("", response_class=FileResponse)
def create_and_download_backup():
    """Create a fresh backup and return it as a downloadable file."""
    path = backup_db(reason="manual")
    if path is None:
        raise HTTPException(status_code=404, detail="Database not found")
    logger.info("Manual backup requested | %s", path.name)
    return FileResponse(
        path=str(path),
        filename=path.name,
        media_type="application/x-sqlite3",
    )


@router.get("/list")
def list_backups():
    """List available backup files."""
    if not BACKUP_DIR.exists():
        return []
    backups = sorted(BACKUP_DIR.glob("dinner_*.db"), key=lambda p: p.name, reverse=True)
    return [
        {"filename": b.name, "size_bytes": b.stat().st_size}
        for b in backups
    ]


@router.get("/download/{filename}", response_class=FileResponse)
def download_backup(filename: str):
    """Download a specific backup file by name."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = BACKUP_DIR / filename
    if not path.exists() or not path.name.startswith("dinner_"):
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/x-sqlite3",
    )
