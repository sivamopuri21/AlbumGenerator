"""
PDF generation using ReportLab (pure Python, no system dependencies).
Generates a landscape A4 PDF with images placed according to layout slots.
"""
import logging
from pathlib import Path
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from PIL import Image

logger = logging.getLogger(__name__)

PAGE_W, PAGE_H = landscape(A4)  # 297mm x 210mm in points


def html_to_pdf(html_path: Path, output_path: Path) -> Path:
    """
    Generate PDF from the album output directory.
    Reads images from the images/ subfolder and places them
    based on the same layout logic used for HTML.
    Falls back to a simple grid if layout info isn't available.
    """
    output_dir = html_path.parent
    img_dir = output_dir / "images"

    if not img_dir.exists():
        logger.error("No images directory found at %s", img_dir)
        raise FileNotFoundError(f"No images directory: {img_dir}")

    # Collect images grouped by page (filenames are p0_s0.jpg, p0_s1.jpg, etc.)
    page_images: dict[int, list[Path]] = {}
    for img_path in sorted(img_dir.iterdir()):
        if not img_path.suffix.lower() in ('.jpg', '.jpeg', '.png'):
            continue
        name = img_path.stem  # e.g. "p0_s0"
        try:
            page_num = int(name.split('_')[0][1:])
        except (ValueError, IndexError):
            page_num = 0
        page_images.setdefault(page_num, []).append(img_path)

    if not page_images:
        logger.error("No images found in %s", img_dir)
        raise FileNotFoundError(f"No images in {img_dir}")

    logger.info("Generating PDF: %d pages, output=%s", len(page_images), output_path)
    c = canvas.Canvas(str(output_path), pagesize=landscape(A4))

    for page_num in sorted(page_images.keys()):
        imgs = page_images[page_num]
        logger.info("PDF page %d: %d images", page_num + 1, len(imgs))
        _draw_page(c, imgs)
        c.showPage()

    c.save()
    size_mb = output_path.stat().st_size / 1e6
    logger.info("PDF saved: %s (%.1f MB, %d pages)", output_path, size_mb, len(page_images))
    return output_path


def _draw_page(c: canvas.Canvas, images: list[Path]):
    """Draw images on a single page using a simple grid layout."""
    n = len(images)
    margin = 10 * mm
    usable_w = PAGE_W - 2 * margin
    usable_h = PAGE_H - 2 * margin

    if n == 1:
        slots = [(margin, margin, usable_w, usable_h)]
    elif n == 2:
        half_w = (usable_w - 5 * mm) / 2
        slots = [
            (margin, margin, half_w, usable_h),
            (margin + half_w + 5 * mm, margin, half_w, usable_h),
        ]
    elif n == 3:
        top_h = usable_h * 0.55
        bot_h = usable_h * 0.40
        gap = usable_h * 0.05
        half_w = (usable_w - 5 * mm) / 2
        slots = [
            (margin, margin + bot_h + gap, usable_w, top_h),
            (margin, margin, half_w, bot_h),
            (margin + half_w + 5 * mm, margin, half_w, bot_h),
        ]
    elif n == 4:
        half_w = (usable_w - 5 * mm) / 2
        half_h = (usable_h - 5 * mm) / 2
        slots = [
            (margin, margin + half_h + 5 * mm, half_w, half_h),
            (margin + half_w + 5 * mm, margin + half_h + 5 * mm, half_w, half_h),
            (margin, margin, half_w, half_h),
            (margin + half_w + 5 * mm, margin, half_w, half_h),
        ]
    else:
        # Generic grid for 5-6 images: 3 columns x 2 rows
        cols = 3
        rows = 2
        gap = 4 * mm
        cell_w = (usable_w - (cols - 1) * gap) / cols
        cell_h = (usable_h - (rows - 1) * gap) / rows
        slots = []
        for i in range(min(n, cols * rows)):
            r, col = divmod(i, cols)
            x = margin + col * (cell_w + gap)
            y = margin + (rows - 1 - r) * (cell_h + gap)
            slots.append((x, y, cell_w, cell_h))

    for i, img_path in enumerate(images):
        if i >= len(slots):
            break
        x, y, w, h = slots[i]
        _draw_image_fit(c, img_path, x, y, w, h)


def _draw_image_fit(c: canvas.Canvas, img_path: Path, x, y, w, h):
    """Draw image maintaining aspect ratio within the given box."""
    try:
        with Image.open(img_path) as img:
            img_w, img_h = img.size
        aspect = img_w / img_h
        box_aspect = w / h
        if aspect > box_aspect:
            draw_w = w
            draw_h = w / aspect
        else:
            draw_h = h
            draw_w = h * aspect
        draw_x = x + (w - draw_w) / 2
        draw_y = y + (h - draw_h) / 2
        c.drawImage(str(img_path), draw_x, draw_y, draw_w, draw_h, preserveAspectRatio=True)
    except Exception as e:
        logger.error("Failed to draw image %s: %s", img_path.name, e)
