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
    # Prevent obvious path traversal characters in the filename
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    base_dir = BACKUP_DIR.resolve()
    try:
        resolved_path = path.resolve()
    except OSError:
        # Path cannot be resolved (e.g. invalid), treat as not found
    # Ensure the resolved path is within the backup directory

    # Ensure the resolved path is inside the backup directory
    try:
        is_within_backup_dir = resolved_path.is_relative_to(BACKUP_DIR)
    except AttributeError:
        # For Python versions without Path.is_relative_to
        is_within_backup_dir = BACKUP_DIR in resolved_path.parents or resolved_path == BACKUP_DIR

    if not is_within_backup_dir:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not resolved_path.exists() or not resolved_path.is_file() or not resolved_path.name.startswith("dinner_"):
        raise HTTPException(status_code=404, detail="Backup not found")

    try:
        path=str(resolved_path),
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
