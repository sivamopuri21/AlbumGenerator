"""
Export Service - Generates PDF and ZIP package from rendered pages.
"""
import logging
import zipfile
from pathlib import Path
from PIL import Image
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from app.models.schemas import AlbumConfig

logger = logging.getLogger(__name__)


def generate_pdf(jpeg_dir: Path, output_path: Path, config: AlbumConfig) -> Path:
    """Generate a combined PDF from all page JPEGs."""
    page_files = sorted(jpeg_dir.glob("page_*.jpg"))
    if not page_files:
        raise FileNotFoundError(f"No page JPEGs found in {jpeg_dir}")

    logger.info("Generating PDF: %d pages, size=%dx%d inches",
                len(page_files), config.width_inches, config.height_inches)

    page_w = config.width_inches * inch
    page_h = config.height_inches * inch

    c = canvas.Canvas(str(output_path), pagesize=(page_w, page_h))

    for page_file in page_files:
        c.drawImage(str(page_file), 0, 0, page_w, page_h)
        c.showPage()

    c.save()
    size_mb = output_path.stat().st_size / 1e6
    logger.info("PDF saved: %s (%.1f MB, %d pages)", output_path.name, size_mb, len(page_files))
    return output_path


def generate_zip(output_dir: Path, config: AlbumConfig) -> Path:
    """Package all outputs into a single ZIP file."""
    zip_path = output_dir / "album_output.zip"
    jpeg_dir = output_dir / "jpeg"
    psd_dir = output_dir / "psd"
    pdf_path = output_dir / "album.pdf"

    logger.info("Creating ZIP package: %s", zip_path)

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add PDF
        if pdf_path.exists():
            zf.write(pdf_path, "album.pdf")
            logger.info("  Added: album.pdf")

        # Add JPEGs
        if jpeg_dir.exists():
            for jpg in sorted(jpeg_dir.glob("page_*.jpg")):
                zf.write(jpg, f"jpeg/{jpg.name}")
            logger.info("  Added: %d JPEG files", len(list(jpeg_dir.glob("page_*.jpg"))))

        # Add PSDs/TIFFs
        if psd_dir.exists():
            for psd in sorted(psd_dir.iterdir()):
                zf.write(psd, f"psd/{psd.name}")
            logger.info("  Added: %d PSD files", len(list(psd_dir.iterdir())))

    size_mb = zip_path.stat().st_size / 1e6
    logger.info("ZIP saved: %s (%.1f MB)", zip_path.name, size_mb)
    return zip_path
