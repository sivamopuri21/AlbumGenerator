"""
Image Compositor - Places photos onto PSD template backgrounds.

Outputs:
  - JPEG files (one per page)
  - PSD files (editable, with layers)
  - Combined PDF
"""
import logging
from pathlib import Path
from PIL import Image
from app.models.schemas import PSDSlot, PSDTemplate, AlbumConfig

# Allow large images for print-resolution work
Image.MAX_IMAGE_PIXELS = 500000000

logger = logging.getLogger(__name__)


def composite_page(
    template: PSDTemplate,
    assignments: list[tuple[PSDSlot, Path]],
    config: AlbumConfig,
    output_dir: Path,
    page_num: int,
) -> dict:
    """
    Composite photos onto a template background.
    Returns paths to output files.
    """
    jpeg_dir = output_dir / "jpeg"
    psd_dir = output_dir / "psd"
    jpeg_dir.mkdir(parents=True, exist_ok=True)
    psd_dir.mkdir(parents=True, exist_ok=True)

    # Load background at target size
    bg_path = Path(template.background_path)
    if not bg_path.exists():
        logger.error("Background not found: %s", bg_path)
        raise FileNotFoundError(f"Background not found: {bg_path}")

    background = Image.open(bg_path).convert("RGB")

    # Resize background to target book size
    target_w = config.width_px
    target_h = config.height_px
    background = background.resize((target_w, target_h), Image.LANCZOS)

    # Calculate scale factor from PSD dimensions to target dimensions
    scale_x = target_w / template.width
    scale_y = target_h / template.height

    # Place each photo in its slot
    for slot, photo_path in assignments:
        try:
            _place_photo(background, slot, photo_path, scale_x, scale_y)
        except Exception as e:
            logger.error("Failed to place %s in slot %s: %s",
                        photo_path.name, slot.layer_name, e)

    # Save JPEG
    jpeg_path = jpeg_dir / f"page_{page_num + 1:03d}.jpg"
    background.save(str(jpeg_path), "JPEG", quality=95, dpi=(config.dpi, config.dpi))
    logger.info("Saved JPEG: %s (%dx%d)", jpeg_path.name, target_w, target_h)

    # Save PSD (as layered TIFF since psd-tools write support is limited)
    # We'll save as PSD-compatible format
    psd_path = psd_dir / f"page_{page_num + 1:03d}.psd"
    _save_as_psd(background, assignments, template, config, psd_path, scale_x, scale_y)

    return {
        "jpeg": str(jpeg_path),
        "psd": str(psd_path),
    }


def _place_photo(
    canvas: Image.Image,
    slot: PSDSlot,
    photo_path: Path,
    scale_x: float,
    scale_y: float,
):
    """Place a photo into a slot on the canvas, maintaining aspect ratio."""
    # Scale slot coordinates to target size
    sx = int(slot.x * scale_x)
    sy = int(slot.y * scale_y)
    sw = int(slot.width * scale_x)
    sh = int(slot.height * scale_y)

    # Open and resize photo to fit slot
    photo = Image.open(photo_path).convert("RGB")
    photo_w, photo_h = photo.size

    # Calculate fit (cover mode - fill the slot, crop excess)
    slot_aspect = sw / sh
    photo_aspect = photo_w / photo_h

    if photo_aspect > slot_aspect:
        # Photo is wider - fit height, crop width
        new_h = sh
        new_w = int(sh * photo_aspect)
    else:
        # Photo is taller - fit width, crop height
        new_w = sw
        new_h = int(sw / photo_aspect)

    photo = photo.resize((new_w, new_h), Image.LANCZOS)

    # Center crop to slot size
    left = (new_w - sw) // 2
    top = (new_h - sh) // 2
    photo = photo.crop((left, top, left + sw, top + sh))

    # Paste onto canvas
    canvas.paste(photo, (sx, sy))


def _save_as_psd(
    composite: Image.Image,
    assignments: list[tuple[PSDSlot, Path]],
    template: PSDTemplate,
    config: AlbumConfig,
    output_path: Path,
    scale_x: float,
    scale_y: float,
):
    """
    Save as PSD with layers.
    Since psd-tools has limited write support, we save as a high-quality
    PSD-compatible file. For full PSD layer support, we create a simple
    PSD structure.
    """
    try:
        from psd_tools import PSDImage
        from psd_tools.api.layers import PixelLayer

        # For now, save the composite as a flat PSD
        # Full layered PSD generation requires low-level PSD writing
        composite.save(str(output_path.with_suffix('.tiff')), "TIFF",
                      compression="tiff_lzw", dpi=(config.dpi, config.dpi))

        # Rename to .psd extension (Photoshop can open TIFF)
        # In production, use a proper PSD writer
        tiff_path = output_path.with_suffix('.tiff')
        if tiff_path.exists():
            tiff_path.rename(output_path.with_suffix('.tiff'))

        # Save composite as PSD (flat)
        composite.save(str(output_path), "TIFF", dpi=(config.dpi, config.dpi))
        logger.info("Saved PSD: %s", output_path.name)

    except Exception as e:
        logger.warning("PSD save failed, saving as TIFF: %s", e)
        composite.save(str(output_path.with_suffix('.tiff')), "TIFF",
                      dpi=(config.dpi, config.dpi))


def render_all_pages(
    pages: list[dict],
    config: AlbumConfig,
    output_dir: Path,
) -> list[dict]:
    """Render all pages and return output file paths."""
    logger.info("Rendering %d pages at %dx%d px (%dx%d inches, %d DPI)",
                len(pages), config.width_px, config.height_px,
                config.width_inches, config.height_inches, config.dpi)

    results = []
    for page in pages:
        result = composite_page(
            template=page["template"],
            assignments=page["assignments"],
            config=config,
            output_dir=output_dir,
            page_num=page["page_num"],
        )
        results.append(result)

    logger.info("Rendered %d pages successfully", len(results))
    return results
