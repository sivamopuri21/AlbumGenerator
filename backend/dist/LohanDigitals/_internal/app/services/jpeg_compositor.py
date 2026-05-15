"""
JPEG Template Compositor - Places new photos onto extracted backgrounds.

Takes the analyzed JPEG template (background + slot positions) and
composites new photos into the detected slots.
"""
import logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 500000000


def composite_jpeg_page(
    template: dict,
    photos: list[Path],
    output_dir: Path,
    page_num: int,
    target_width: int = 0,
    target_height: int = 0,
) -> dict:
    """
    Place photos onto a JPEG template background.
    
    Args:
        template: Output from analyze_jpeg_template()
        photos: List of photo paths to place
        output_dir: Where to save output
        page_num: Page number for filename
        target_width/height: If set, resize output to these dimensions
    """
    jpeg_dir = output_dir / "jpeg"
    jpeg_dir.mkdir(parents=True, exist_ok=True)

    # Load background
    bg_path = template["background_path"]
    background = cv2.imread(bg_path)
    if background is None:
        raise ValueError(f"Cannot load background: {bg_path}")

    orig_h, orig_w = background.shape[:2]
    slots = template["slots"]

    # Place photos into slots
    for i, slot in enumerate(slots):
        if i >= len(photos):
            break
        photo_path = photos[i]
        _place_photo_cv2(background, slot, photo_path)
        logger.debug("  Placed %s in slot %d (%s)",
                    photo_path.name, i+1, slot["layer_name"])

    # Resize to target if specified
    if target_width > 0 and target_height > 0:
        background = cv2.resize(background, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)

    # Save JPEG output
    jpeg_path = jpeg_dir / f"page_{page_num:03d}.jpg"
    cv2.imwrite(str(jpeg_path), background, [cv2.IMWRITE_JPEG_QUALITY, 95])
    logger.info("  Saved page %d: %s", page_num, jpeg_path.name)

    return {"jpeg": str(jpeg_path), "page_num": page_num}


def _place_photo_cv2(
    canvas: np.ndarray,
    slot: dict,
    photo_path: Path,
):
    """Place a photo into a slot using OpenCV (cover mode with center crop)."""
    x, y, w, h = slot["x"], slot["y"], slot["width"], slot["height"]

    # Read photo
    photo = cv2.imread(str(photo_path))
    if photo is None:
        logger.warning("Cannot read photo: %s", photo_path)
        return

    ph, pw = photo.shape[:2]

    # Calculate cover crop (fill slot, maintain aspect ratio)
    slot_aspect = w / h
    photo_aspect = pw / ph

    if photo_aspect > slot_aspect:
        # Photo is wider - fit height, crop width
        new_h = h
        new_w = int(h * photo_aspect)
    else:
        # Photo is taller - fit width, crop height
        new_w = w
        new_h = int(w / photo_aspect)

    photo = cv2.resize(photo, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # Center crop
    crop_x = (new_w - w) // 2
    crop_y = (new_h - h) // 2
    photo = photo[crop_y:crop_y+h, crop_x:crop_x+w]

    # Ensure we don't go out of canvas bounds
    canvas_h, canvas_w = canvas.shape[:2]
    if x < 0:
        photo = photo[:, -x:]
        w += x
        x = 0
    if y < 0:
        photo = photo[-y:, :]
        h += y
        y = 0
    if x + w > canvas_w:
        w = canvas_w - x
        photo = photo[:, :w]
    if y + h > canvas_h:
        h = canvas_h - y
        photo = photo[:h, :]

    # Place on canvas
    if photo.shape[0] > 0 and photo.shape[1] > 0:
        canvas[y:y+h, x:x+w] = photo[:h, :w]


def render_all_jpeg_pages(
    templates: list[dict],
    photos: list[Path],
    output_dir: Path,
    total_pages: int,
    target_width: int = 0,
    target_height: int = 0,
) -> list[dict]:
    """
    Render all pages using JPEG templates.
    Distributes photos across templates and composites them.
    """
    logger.info("Rendering %d pages from %d JPEG templates with %d photos",
                total_pages, len(templates), len(photos))

    results = []
    photo_idx = 0

    for page_num in range(1, total_pages + 1):
        # Cycle through templates
        template = templates[(page_num - 1) % len(templates)]
        slot_count = len(template["slots"])

        # Get photos for this page
        page_photos = photos[photo_idx:photo_idx + slot_count]
        photo_idx += slot_count

        if not page_photos:
            logger.warning("  No more photos for page %d", page_num)
            break

        result = composite_jpeg_page(
            template=template,
            photos=page_photos,
            output_dir=output_dir,
            page_num=page_num,
            target_width=target_width,
            target_height=target_height,
        )
        results.append(result)

    logger.info("Rendered %d pages", len(results))
    return results
