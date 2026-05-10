"""
File Cleanup Service - Deletes files older than today on startup.
Keeps only today's uploads and outputs.
"""
import logging
import shutil
from datetime import datetime, date
from pathlib import Path
from app.config import UPLOAD_PATH, OUTPUT_PATH

logger = logging.getLogger(__name__)


def cleanup_old_files():
    """Delete all upload and output files from before today."""
    today = date.today()
    deleted_count = 0
    freed_bytes = 0

    for base_dir in [UPLOAD_PATH, OUTPUT_PATH]:
        if not base_dir.exists():
            continue
        for item in base_dir.iterdir():
            try:
                # Get modification time
                mtime = datetime.fromtimestamp(item.stat().st_mtime).date()
                if mtime < today:
                    size = _get_size(item)
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    deleted_count += 1
                    freed_bytes += size
                    logger.info("Deleted old file: %s (from %s)", item.name, mtime)
            except Exception as e:
                logger.warning("Failed to delete %s: %s", item.name, e)

    if deleted_count > 0:
        logger.info("Cleanup complete: deleted %d items, freed %.1f MB",
                    deleted_count, freed_bytes / 1e6)
    else:
        logger.info("Cleanup: nothing to delete, all files are from today")


def _get_size(path: Path) -> int:
    """Get total size of a file or directory."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total
