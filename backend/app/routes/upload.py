import uuid
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from app.config import settings, UPLOAD_PATH
from app.models.schemas import BookSize
from app.models.job_store import job_store
from app.services.pipeline import run_pipeline, run_pipeline_mode2

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
}
ALLOWED_TEMPLATE_TYPES = {
    "application/octet-stream",  # PSD files often come as this
    "image/vnd.adobe.photoshop",
    "application/x-photoshop",
    "application/photoshop",
}
MAX_FILE_SIZE = settings.max_upload_size_mb * 1024 * 1024


@router.post("/upload")
async def upload_and_generate(
    background_tasks: BackgroundTasks,
    book_size: str = Form(...),
    num_sheets: int = Form(...),
    images: list[UploadFile] = File(...),
    templates: Optional[list[UploadFile]] = File(None),
):
    """Upload images + PSD templates, start album generation."""
    # Validate book size
    try:
        size = BookSize(book_size)
    except ValueError:
        raise HTTPException(400, f"Invalid book size: {book_size}. Use: 12x36, 18x24, 18x26")

    # Validate sheet count
    if num_sheets < 1 or num_sheets > 100:
        raise HTTPException(400, "Sheet count must be between 1 and 100")

    if not images:
        raise HTTPException(400, "No images provided")
    if len(images) > settings.max_images:
        raise HTTPException(400, f"Max {settings.max_images} images allowed")

    if templates is None:
        templates = []

    # Validate minimum photos for the requested pages
    total_pages = num_sheets * 2
    if len(images) < total_pages:
        logger.warning("Only %d images for %d pages - some pages may be sparse", len(images), total_pages)

    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOAD_PATH / job_id
    img_dir = job_dir / "images"
    tmpl_dir = job_dir / "templates"
    img_dir.mkdir(parents=True, exist_ok=True)
    tmpl_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded images
    logger.info("Job %s: saving %d images...", job_id, len(images))
    saved_bytes = 0
    for f in images:
        if f.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(400, f"Unsupported image type: {f.content_type} ({f.filename})")
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large: {f.filename}")
        (img_dir / f.filename).write_bytes(data)
        saved_bytes += len(data)
    logger.info("Job %s: %d images saved (%.1f MB)", job_id, len(images), saved_bytes / 1e6)

    # Save PSD templates
    if templates:
        logger.info("Job %s: saving %d templates...", job_id, len(templates))
        has_psd = False
        has_jpeg = False
        for f in templates:
            fname_lower = f.filename.lower()
            if fname_lower.endswith('.psd'):
                has_psd = True
            elif fname_lower.endswith(('.jpg', '.jpeg', '.png')):
                has_jpeg = True
            else:
                raise HTTPException(400, f"Templates must be PSD or JPEG files: {f.filename}")
            data = await f.read()
            (tmpl_dir / f.filename).write_bytes(data)
        logger.info("Job %s: %d templates saved (PSD=%s, JPEG=%s)", job_id, len(templates), has_psd, has_jpeg)
    else:
        logger.warning("Job %s: no templates uploaded", job_id)
        has_psd = False
        has_jpeg = False

    # Create job and start pipeline
    job_store.create(job_id, total_images=len(images))
    job_store.update(job_id, book_size=book_size, total_sheets=num_sheets, total_pages=total_pages)

    # Choose pipeline mode based on template type
    if has_jpeg:
        mode = "mode2"
        logger.info("Job %s: using Mode 2 (JPEG templates)", job_id)
        background_tasks.add_task(run_pipeline_mode2, job_id, img_dir, tmpl_dir, size, num_sheets)
    else:
        mode = "mode1"
        logger.info("Job %s: using Mode 1 (PSD templates)", job_id)
        background_tasks.add_task(run_pipeline, job_id, img_dir, tmpl_dir, size, num_sheets)

    return {
        "job_id": job_id,
        "message": "Processing started",
        "mode": mode,
        "book_size": book_size,
        "num_sheets": num_sheets,
        "total_pages": total_pages,
        "total_images": len(images),
        "total_templates": len(templates),
    }
