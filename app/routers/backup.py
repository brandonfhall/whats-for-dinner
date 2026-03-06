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
    # Prevent obvious path traversal attempts in the raw filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    base_dir = BACKUP_DIR.resolve()
    path = (base_dir / filename).resolve()
    # Ensure the resolved path is within the backup directory
    try:
        is_within_base = path.is_relative_to(base_dir)
    except AttributeError:
        # Fallback for Python versions without Path.is_relative_to
        is_within_base = base_dir == path or base_dir in path.parents
    if not is_within_base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists() or not path.name.startswith("dinner_"):
        raise HTTPException(status_code=404, detail="Backup not found")
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/x-sqlite3",
    )
