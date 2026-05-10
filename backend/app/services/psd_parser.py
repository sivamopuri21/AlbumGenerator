"""
PSD Template Parser - Extracts backgrounds and photo slot positions from PSD files.
Optimized for large print-resolution PSDs (18000+ px).
"""
import logging
import time
from pathlib import Path
from PIL import Image
from psd_tools import PSDImage
from app.models.schemas import PSDTemplate, PSDSlot

# Allow large images (print-resolution PSDs can be 200+ megapixels)
Image.MAX_IMAGE_PIXELS = 500000000  # 500MP limit

logger = logging.getLogger(__name__)

SLOT_KEYWORDS = ["photo", "slot", "image", "placeholder", "picture", "img"]
BACKGROUND_KEYWORDS = ["background", "bg", "base", "backdrop"]
IGNORE_KEYWORDS = ["decoration", "decor", "text", "title", "overlay", "frame", "border"]


def parse_psd_template(psd_path: Path, output_dir: Path) -> PSDTemplate:
    """Parse a PSD file: extract background + detect photo slots."""
    start = time.time()
    logger.info("Parsing PSD: %s", psd_path.name)
    output_dir.mkdir(parents=True, exist_ok=True)

    psd = PSDImage.open(str(psd_path))
    width, height = psd.width, psd.height
    logger.info("  Dimensions: %dx%d (%.1f MP)", width, height, width * height / 1e6)

    # List all layers for debugging
    logger.info("  Layers in %s:", psd_path.name)
    for layer in psd:
        logger.info("    - '%s' visible=%s bbox=%s kind=%s",
                    layer.name, layer.is_visible(), layer.bbox,
                    getattr(layer, 'kind', 'unknown'))

    # Extract slots first (fast - just reads layer metadata)
    slots = _extract_slots(psd, width, height)

    # If no named slots, detect by geometry
    if not slots:
        logger.info("  No named slots, detecting by geometry...")
        slots = _detect_slots_by_geometry(psd, width, height)

    # Extract background (slow for large files)
    bg_path = output_dir / f"{psd_path.stem}_bg.jpg"
    logger.info("  Extracting background (this may take a moment for large files)...")
    _extract_background(psd, bg_path)

    elapsed = time.time() - start
    logger.info("  DONE: %s - %d slots found in %.1fs", psd_path.name, len(slots), elapsed)

    for i, slot in enumerate(slots):
        logger.info("    Slot %d: '%s' (%d,%d) %dx%d [%s]",
                    i + 1, slot.layer_name, slot.x, slot.y,
                    slot.width, slot.height, slot.orientation)

    return PSDTemplate(
        filename=psd_path.name,
        width=width,
        height=height,
        slots=slots,
        background_path=str(bg_path),
        slot_count=len(slots),
    )


def _extract_background(psd: PSDImage, output_path: Path):
    """Extract background - convert RGBA to RGB, save as JPEG."""
    try:
        composite = psd.composite()
        # Convert RGBA to RGB (JPEG doesn't support transparency)
        if composite.mode in ('RGBA', 'LA', 'P'):
            # Create white background and paste with alpha
            bg = Image.new('RGB', composite.size, (255, 255, 255))
            if composite.mode == 'RGBA':
                bg.paste(composite, mask=composite.split()[3])
            else:
                bg.paste(composite.convert('RGBA'), mask=composite.convert('RGBA').split()[3])
            composite = bg
        elif composite.mode != 'RGB':
            composite = composite.convert('RGB')
        composite.save(str(output_path), "JPEG", quality=85)
        logger.info("  Background saved: %s", output_path.name)
    except Exception as e:
        logger.error("  Background extraction failed: %s", e)
        # Create a blank background as fallback
        img = Image.new('RGB', (psd.width, psd.height), (255, 255, 255))
        img.save(str(output_path), "JPEG", quality=85)


def _extract_slots(psd: PSDImage, psd_w: int, psd_h: int) -> list[PSDSlot]:
    """Find photo slots by layer name keywords."""
    slots = []
    for layer in psd:
        if not layer.is_visible():
            continue
        name_lower = layer.name.lower()
        if any(kw in name_lower for kw in IGNORE_KEYWORDS):
            continue
        if any(kw in name_lower for kw in BACKGROUND_KEYWORDS):
            continue

        is_slot = any(kw in name_lower for kw in SLOT_KEYWORDS)
        if is_slot and layer.bbox != (0, 0, 0, 0):
            x, y, x2, y2 = layer.bbox
            w, h = x2 - x, y2 - y
            if w > 100 and h > 100:
                slots.append(PSDSlot(
                    layer_name=layer.name,
                    x=x, y=y, width=w, height=h,
                    orientation=_get_orientation(w, h),
                ))
    slots.sort(key=lambda s: (s.y, s.x))
    return slots


def _detect_slots_by_geometry(psd: PSDImage, psd_w: int, psd_h: int) -> list[PSDSlot]:
    """Auto-detect slots: any visible non-background layer > 5% of page area."""
    slots = []
    psd_area = psd_w * psd_h

    for layer in psd:
        if not layer.is_visible():
            continue
        name_lower = layer.name.lower()
        if any(kw in name_lower for kw in BACKGROUND_KEYWORDS):
            continue
        if layer.bbox == (0, 0, 0, 0):
            continue

        x, y, x2, y2 = layer.bbox
        w, h = x2 - x, y2 - y

        # Skip if it covers the entire canvas (it's a background)
        if w >= psd_w * 0.95 and h >= psd_h * 0.95:
            continue

        # Must be at least 5% of page and 200px minimum
        if (w * h) > psd_area * 0.05 and w > 200 and h > 200:
            slots.append(PSDSlot(
                layer_name=layer.name,
                x=x, y=y, width=w, height=h,
                orientation=_get_orientation(w, h),
            ))
            logger.info("    Auto-detected: '%s' (%d,%d) %dx%d", layer.name, x, y, w, h)

    slots.sort(key=lambda s: (s.y, s.x))
    return slots


def _get_orientation(w: int, h: int) -> str:
    if w > h * 1.2:
        return "landscape"
    elif h > w * 1.2:
        return "portrait"
    return "square"


def parse_all_templates(psd_dir: Path, output_dir: Path) -> list[PSDTemplate]:
    """Parse all PSD files with per-file progress logging."""
    psd_files = sorted(psd_dir.glob("*.psd"))
    logger.info("=" * 50)
    logger.info("PARSING %d PSD TEMPLATES", len(psd_files))
    logger.info("=" * 50)

    templates = []
    for i, psd_path in enumerate(psd_files):
        logger.info("[%d/%d] Processing: %s", i + 1, len(psd_files), psd_path.name)
        try:
            template = parse_psd_template(psd_path, output_dir)
            if template.slot_count == 0:
                logger.warning("  WARNING: %s has 0 slots - will use as full-page background", psd_path.name)
            templates.append(template)
        except Exception as e:
            logger.error("  FAILED: %s - %s", psd_path.name, e)

    logger.info("=" * 50)
    logger.info("PARSING COMPLETE: %d/%d templates OK, %d total slots",
                len(templates), len(psd_files),
                sum(t.slot_count for t in templates))
    logger.info("=" * 50)
    return templates
