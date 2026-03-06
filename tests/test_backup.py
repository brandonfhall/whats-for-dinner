"""Tests for the database backup functionality."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from app.database import backup_db, _weekly_backup, BACKUP_DIR


def _create_test_db(path):
    """Create a minimal valid SQLite database."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO test VALUES (1)")
    conn.commit()
    conn.close()


def test_backup_creates_file(tmp_path):
    """backup_db creates a timestamped copy of the database."""
    src = tmp_path / "test.db"
    _create_test_db(src)
    backup_dir = tmp_path / "backups"

    with patch("app.database.DB_PATH", str(src)), \
         patch("app.database.BACKUP_DIR", backup_dir), \
         patch("app.database.MAX_BACKUPS", 5):
        result = backup_db(reason="test")

    assert result is not None
    assert result.exists()
    assert result.name.startswith("dinner_test_")
    assert result.suffix == ".db"
    # Verify the backup is a valid SQLite database
    conn = sqlite3.connect(result)
    row = conn.execute("SELECT COUNT(*) FROM test").fetchone()
    conn.close()
    assert row[0] == 1


def test_backup_returns_none_if_no_db(tmp_path):
    """backup_db returns None if the source database doesn't exist."""
    with patch("app.database.DB_PATH", str(tmp_path / "nonexistent.db")):
        result = backup_db(reason="test")
    assert result is None


def test_backup_prunes_old_files(tmp_path):
    """backup_db keeps only MAX_BACKUPS files per reason."""
    src = tmp_path / "test.db"
    _create_test_db(src)
    backup_dir = tmp_path / "backups"

    with patch("app.database.DB_PATH", str(src)), \
         patch("app.database.BACKUP_DIR", backup_dir), \
         patch("app.database.MAX_BACKUPS", 2):
        # Create 3 backups — only 2 should remain
        for i in range(3):
            backup_db(reason="prune")

    remaining = list(backup_dir.glob("dinner_prune_*.db"))
    assert len(remaining) == 2


def test_backup_api_list_empty(client):
    """GET /api/backup/list returns empty list when no backups exist."""
    with patch("app.routers.backup.BACKUP_DIR", Path("/nonexistent")):
        r = client.get("/api/backup/list")
    assert r.status_code == 200
    assert r.json() == []


def test_backup_api_download_not_found(client):
    """GET /api/backup/download/missing.db returns 404."""
    with patch("app.routers.backup.BACKUP_DIR", Path("/nonexistent")):
        r = client.get("/api/backup/download/missing.db")
    assert r.status_code == 404


def test_backup_api_download_rejects_non_dinner_prefix(client, tmp_path):
    """GET /api/backup/download rejects files that don't start with 'dinner_'."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "evil.db").write_text("nope")
    with patch("app.routers.backup.BACKUP_DIR", backup_dir):
        r = client.get("/api/backup/download/evil.db")
    assert r.status_code == 404


def test_weekly_backup_creates_file(tmp_path):
    """_weekly_backup creates one backup per calendar week."""
    src = tmp_path / "test.db"
    _create_test_db(src)
    backup_dir = tmp_path / "backups"

    with patch("app.database.DB_PATH", str(src)), \
         patch("app.database.BACKUP_DIR", backup_dir), \
         patch("app.database.MAX_BACKUPS", 5):
        _weekly_backup()

    weeklies = list(backup_dir.glob("dinner_weekly_*.db"))
    assert len(weeklies) == 1


def test_weekly_backup_skips_if_already_exists(tmp_path):
    """_weekly_backup does not create a second backup in the same week."""
    src = tmp_path / "test.db"
    _create_test_db(src)
    backup_dir = tmp_path / "backups"

    with patch("app.database.DB_PATH", str(src)), \
         patch("app.database.BACKUP_DIR", backup_dir), \
         patch("app.database.MAX_BACKUPS", 5):
        _weekly_backup()
        _weekly_backup()  # should be a no-op

    weeklies = list(backup_dir.glob("dinner_weekly_*.db"))
    assert len(weeklies) == 1


def test_weekly_backup_prunes_old_weeks(tmp_path):
    """_weekly_backup keeps only MAX_BACKUPS weekly backups."""
    src = tmp_path / "test.db"
    _create_test_db(src)
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)

    # Create 6 fake weekly backups from different weeks
    for i in range(6):
        (backup_dir / f"dinner_weekly_2026_W{i:02d}_20260101_000000_000000.db").write_bytes(b"x")

    with patch("app.database.DB_PATH", str(src)), \
         patch("app.database.BACKUP_DIR", backup_dir), \
         patch("app.database.MAX_BACKUPS", 5):
        _weekly_backup()  # creates a 7th, should prune to 5

    weeklies = list(backup_dir.glob("dinner_weekly_*.db"))
    assert len(weeklies) == 5
