"""
Album Generation Pipeline - Orchestrates the full flow.
Supports two modes:
  Mode 1: PSD templates + raw photos
  Mode 2: JPEG album pages (as templates) + raw photos
"""
import logging
from pathlib import Path
from app.models.schemas import (
    JobStatus, AlbumConfig, BookSize, BOOK_DIMENSIONS,
)
from app.models.job_store import job_store
from app.services.image_processor import preprocess_images
from app.services.clip_service import deduplicate_images
from app.services.quality_filter import filter_quality
from app.services.face_ranker import rank_by_faces
from app.services.psd_parser import parse_all_templates
from app.services.photo_matcher import distribute_photos_to_pages
from app.services.jpeg_template_analyzer import analyze_all_jpeg_templates
from app.services.jpeg_compositor import render_all_jpeg_pages

def _get_orientation(w: int, h: int) -> str:
    if w > h * 1.2:
        return "landscape"
    elif h > w * 1.2:
        return "portrait"
    return "square"
from app.services.compositor import render_all_pages
from app.services.exporter import generate_pdf, generate_zip
from app.config import OUTPUT_PATH

logger = logging.getLogger(__name__)


def build_config(book_size: BookSize, num_sheets: int, dpi: int = 300) -> AlbumConfig:
    """Build album configuration from user inputs."""
    w_inches, h_inches = BOOK_DIMENSIONS[book_size]
    return AlbumConfig(
        book_size=book_size,
        num_sheets=num_sheets,
        total_pages=num_sheets * 2,
        width_inches=w_inches,
        height_inches=h_inches,
        width_px=int(w_inches * dpi),
        height_px=int(h_inches * dpi),
        dpi=dpi,
    )


def run_pipeline(
    job_id: str,
    image_dir: Path,
    template_dir: Path,
    book_size: BookSize,
    num_sheets: int,
) -> Path:
    """Full album generation pipeline. Returns path to output ZIP."""
    try:
        config = build_config(book_size, num_sheets)
        logger.info("=" * 60)
        logger.info("PIPELINE START: job=%s", job_id)
        logger.info("  Book size: %s (%dx%d inches, %dx%d px)",
                    book_size.value, config.width_inches, config.height_inches,
                    config.width_px, config.height_px)
        logger.info("  Sheets: %d -> %d pages", num_sheets, config.total_pages)
        logger.info("=" * 60)

        job_store.update(job_id, book_size=book_size.value,
                        total_sheets=num_sheets, total_pages=config.total_pages)

        # Step 1: Parse PSD templates
        _update(job_id, JobStatus.PARSING_TEMPLATES, 5, "Parsing PSD templates...")
        template_output = OUTPUT_PATH / job_id / "template_assets"
        templates = parse_all_templates(template_dir, template_output)
        if not templates:
            raise ValueError("No valid PSD templates found")

        # For templates with 0 slots, create default centered slots
        for t in templates:
            if t.slot_count == 0:
                from app.models.schemas import PSDSlot
                # Create a default slot covering 80% of the page, centered
                margin_x = int(t.width * 0.1)
                margin_y = int(t.height * 0.1)
                default_slot = PSDSlot(
                    layer_name="auto_slot_1",
                    x=margin_x, y=margin_y,
                    width=t.width - 2 * margin_x,
                    height=t.height - 2 * margin_y,
                    orientation=_get_orientation(t.width, t.height),
                )
                t.slots = [default_slot]
                t.slot_count = 1
                logger.info("Added default slot to %s: %dx%d at (%d,%d)",
                           t.filename, default_slot.width, default_slot.height,
                           default_slot.x, default_slot.y)

        _update(job_id, JobStatus.PARSING_TEMPLATES, 10,
                f"Parsed {len(templates)} templates ({sum(t.slot_count for t in templates)} total slots)")

        # Step 2: Preprocess images
        _update(job_id, JobStatus.PREPROCESSING, 15, "Preprocessing images...")
        images = preprocess_images(image_dir)
        if not images:
            raise ValueError("No valid images after preprocessing")
        _update(job_id, JobStatus.PREPROCESSING, 25, f"{len(images)} images preprocessed")

        # Step 3: Deduplicate
        _update(job_id, JobStatus.DEDUPLICATING, 30, "Removing duplicates...")
        images = deduplicate_images(images)
        _update(job_id, JobStatus.DEDUPLICATING, 35, f"{len(images)} unique images")

        # Step 4: Quality filter
        _update(job_id, JobStatus.FILTERING, 40, "Filtering quality...")
        images = filter_quality(images)
        if not images:
            raise ValueError("No images passed quality filter")
        _update(job_id, JobStatus.FILTERING, 45, f"{len(images)} quality images")

        # Step 5: Face detection & ranking
        _update(job_id, JobStatus.DETECTING_FACES, 50, "Detecting faces...")
        ranked = rank_by_faces(images)
        face_counts = {p.name: fc for p, fc in ranked}
        images = [p for p, _ in ranked]
        _update(job_id, JobStatus.DETECTING_FACES, 60, f"Face detection complete ({sum(1 for _,f in ranked if f > 0)} with faces)")

        # Step 6: Assign photos to pages
        _update(job_id, JobStatus.ASSIGNING_PHOTOS, 65, "Assigning photos to templates...")
        pages = distribute_photos_to_pages(images, templates, config.total_pages, face_counts)
        if not pages:
            raise ValueError("Could not assign photos to any pages")
        _update(job_id, JobStatus.ASSIGNING_PHOTOS, 70, f"{len(pages)} pages assigned")

        # Step 7: Render (composite photos onto backgrounds)
        _update(job_id, JobStatus.RENDERING, 75, "Rendering pages...")
        out_dir = OUTPUT_PATH / job_id
        render_all_pages(pages, config, out_dir)
        _update(job_id, JobStatus.RENDERING, 85, "All pages rendered")

        # Step 8: Generate PDF
        _update(job_id, JobStatus.EXPORTING, 88, "Generating PDF...")
        jpeg_dir = out_dir / "jpeg"
        pdf_path = out_dir / "album.pdf"
        generate_pdf(jpeg_dir, pdf_path, config)

        # Step 9: Create ZIP package
        _update(job_id, JobStatus.EXPORTING, 92, "Creating download package...")
        zip_path = generate_zip(out_dir, config)

        _update(job_id, JobStatus.COMPLETED, 100, "Album complete!")
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE: job=%s, output=%s", job_id, zip_path)
        logger.info("=" * 60)
        return zip_path

    except Exception as e:
        logger.exception("Pipeline failed for job %s", job_id)
        job_store.update(job_id, status=JobStatus.FAILED, error=str(e))
        raise


def _update(job_id: str, status: JobStatus, progress: float, message: str):
    job_store.update(job_id, status=status, progress=progress, message=message)
    logger.info("[%s] %s (%.0f%%): %s", job_id, status.value, progress, message)


def run_pipeline_mode2(
    job_id: str,
    image_dir: Path,
    template_dir: Path,
    book_size: BookSize,
    num_sheets: int,
) -> Path:
    """
    Mode 2 Pipeline: JPEG album pages as templates.
    Analyzes existing album pages, extracts backgrounds, places new photos.
    """
    try:
        config = build_config(book_size, num_sheets)
        logger.info("=" * 60)
        logger.info("PIPELINE MODE 2 START: job=%s", job_id)
        logger.info("  Book size: %s (%dx%d inches)", book_size.value, config.width_inches, config.height_inches)
        logger.info("  Sheets: %d -> %d pages", num_sheets, config.total_pages)
        logger.info("=" * 60)

        job_store.update(job_id, book_size=book_size.value,
                        total_sheets=num_sheets, total_pages=config.total_pages)

        # Step 1: Analyze JPEG templates
        _update(job_id, JobStatus.PARSING_TEMPLATES, 5, "Analyzing album pages...")
        template_output = OUTPUT_PATH / job_id / "template_assets"
        templates = analyze_all_jpeg_templates(template_dir, template_output)
        if not templates:
            raise ValueError("No valid JPEG templates found")
        total_slots = sum(len(t["slots"]) for t in templates)
        _update(job_id, JobStatus.PARSING_TEMPLATES, 15,
                f"Analyzed {len(templates)} pages ({total_slots} photo slots detected)")

        # Step 2: Preprocess raw images
        _update(job_id, JobStatus.PREPROCESSING, 20, "Preprocessing images...")
        images = preprocess_images(image_dir)
        if not images:
            raise ValueError("No valid images after preprocessing")
        _update(job_id, JobStatus.PREPROCESSING, 30, f"{len(images)} images preprocessed")

        # Step 3: Deduplicate
        _update(job_id, JobStatus.DEDUPLICATING, 35, "Removing duplicates...")
        images = deduplicate_images(images)
        _update(job_id, JobStatus.DEDUPLICATING, 40, f"{len(images)} unique images")

        # Step 4: Quality filter
        _update(job_id, JobStatus.FILTERING, 45, "Filtering quality...")
        images = filter_quality(images)
        if not images:
            raise ValueError("No images passed quality filter")
        _update(job_id, JobStatus.FILTERING, 50, f"{len(images)} quality images")

        # Step 5: Face detection
        _update(job_id, JobStatus.DETECTING_FACES, 55, "Detecting faces...")
        ranked = rank_by_faces(images)
        images = [p for p, _ in ranked]
        _update(job_id, JobStatus.DETECTING_FACES, 65, "Face detection complete")

        # Step 6: Render pages (composite new photos onto extracted backgrounds)
        _update(job_id, JobStatus.RENDERING, 70, "Rendering pages...")
        out_dir = OUTPUT_PATH / job_id
        render_all_jpeg_pages(
            templates=templates,
            photos=images,
            output_dir=out_dir,
            total_pages=config.total_pages,
            target_width=config.width_px,
            target_height=config.height_px,
        )
        _update(job_id, JobStatus.RENDERING, 85, "All pages rendered")

        # Step 7: Generate PDF
        _update(job_id, JobStatus.EXPORTING, 88, "Generating PDF...")
        from app.services.exporter import generate_pdf, generate_zip
        jpeg_dir = out_dir / "jpeg"
        pdf_path = out_dir / "album.pdf"
        generate_pdf(jpeg_dir, pdf_path, config)

        # Step 8: Create ZIP
        _update(job_id, JobStatus.EXPORTING, 92, "Creating download package...")
        zip_path = generate_zip(out_dir, config)

        _update(job_id, JobStatus.COMPLETED, 100, "Album complete!")
        logger.info("=" * 60)
        logger.info("PIPELINE MODE 2 COMPLETE: job=%s", job_id)
        logger.info("=" * 60)
        return zip_path

    except Exception as e:
        logger.exception("Pipeline Mode 2 failed for job %s", job_id)
        job_store.update(job_id, status=JobStatus.FAILED, error=str(e))
        raise
