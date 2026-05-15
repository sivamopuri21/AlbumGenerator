"""
JPEG Template Analyzer - Detects photo regions in existing album pages.

Takes an existing album page (JPEG) and:
1. Detects rectangular photo regions using edge detection + contour analysis
2. Extracts the background by inpainting over photo regions
3. Returns slot positions for placing new photos

Approach:
- Convert to grayscale, apply edge detection
- Find large rectangular contours (these are photo boundaries)
- Use color variance to confirm regions contain photos (high variance = photo, low = background)
- Inpaint the photo regions to recover the background
"""
import logging
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Allow large images
Image.MAX_IMAGE_PIXELS = 500000000

MIN_PHOTO_AREA_RATIO = 0.03  # Minimum 3% of page area to be a photo
MAX_PHOTO_AREA_RATIO = 0.70  # Maximum 70% of page area
MIN_DIMENSION = 100  # Minimum pixel dimension for a photo region


def analyze_jpeg_template(
    jpeg_path: Path,
    output_dir: Path,
) -> dict:
    """
    Analyze a JPEG album page to detect photo regions and extract background.
    
    Returns:
        {
            "background_path": str,
            "slots": [{"x": int, "y": int, "width": int, "height": int, "orientation": str}],
            "original_width": int,
            "original_height": int,
        }
    """
    logger.info("Analyzing JPEG template: %s", jpeg_path.name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load image
    img = cv2.imread(str(jpeg_path))
    if img is None:
        raise ValueError(f"Cannot read image: {jpeg_path}")

    height, width = img.shape[:2]
    logger.info("  Image size: %dx%d", width, height)
    page_area = width * height

    # Step 1: Detect photo regions
    slots = _detect_photo_regions(img, width, height, page_area)
    logger.info("  Detected %d photo regions", len(slots))

    # Step 2: Extract background by inpainting photo regions
    bg_path = output_dir / f"{jpeg_path.stem}_bg.jpg"
    _extract_background(img, slots, bg_path)
    logger.info("  Background saved: %s", bg_path.name)

    # Step 3: Format slot info
    slot_list = []
    for i, (x, y, w, h) in enumerate(slots):
        orientation = "landscape" if w > h * 1.2 else ("portrait" if h > w * 1.2 else "square")
        slot_list.append({
            "x": x, "y": y, "width": w, "height": h,
            "orientation": orientation,
            "layer_name": f"photo_{i+1}",
        })
        logger.info("    Slot %d: (%d,%d) %dx%d [%s]", i+1, x, y, w, h, orientation)

    return {
        "background_path": str(bg_path),
        "slots": slot_list,
        "original_width": width,
        "original_height": height,
        "filename": jpeg_path.name,
    }


def _detect_photo_regions(
    img: np.ndarray,
    width: int,
    height: int,
    page_area: int,
) -> list[tuple[int, int, int, int]]:
    """
    Detect rectangular photo regions using multiple strategies:
    1. Edge detection + contour finding
    2. Color variance analysis to confirm
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Strategy 1: Canny edge detection + contours
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)

    # Dilate edges to close gaps
    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=2)
    edges = cv2.erode(edges, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        # Approximate to polygon
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        area_ratio = area / page_area

        # Filter by size
        if area_ratio < MIN_PHOTO_AREA_RATIO or area_ratio > MAX_PHOTO_AREA_RATIO:
            continue
        if w < MIN_DIMENSION or h < MIN_DIMENSION:
            continue

        # Check if region has high color variance (indicates a photo)
        region = img[y:y+h, x:x+w]
        variance = np.var(region)
        if variance > 500:  # Photos have high variance, solid backgrounds don't
            candidates.append((x, y, w, h, area, variance))

    # If edge detection didn't find enough, try adaptive thresholding
    if len(candidates) < 1:
        candidates = _detect_by_variance_grid(img, width, height, page_area)

    # Remove overlapping regions (keep larger ones)
    candidates.sort(key=lambda c: c[4], reverse=True)  # Sort by area
    filtered = _remove_overlaps(candidates)

    # Return just (x, y, w, h)
    return [(x, y, w, h) for x, y, w, h, _, _ in filtered]


def _detect_by_variance_grid(
    img: np.ndarray,
    width: int,
    height: int,
    page_area: int,
) -> list[tuple[int, int, int, int, int, float]]:
    """
    Fallback: divide image into grid and find high-variance blocks.
    Then merge adjacent high-variance blocks into photo regions.
    """
    block_size = max(width, height) // 20
    if block_size < 50:
        block_size = 50

    variance_map = np.zeros((height // block_size + 1, width // block_size + 1), dtype=np.float32)

    for row in range(0, height - block_size, block_size):
        for col in range(0, width - block_size, block_size):
            block = img[row:row+block_size, col:col+block_size]
            variance_map[row // block_size, col // block_size] = np.var(block)

    # Threshold: blocks with variance > median * 1.5 are likely photos
    median_var = np.median(variance_map[variance_map > 0])
    threshold = median_var * 1.5

    # Create binary mask of photo regions
    mask = (variance_map > threshold).astype(np.uint8) * 255

    # Find contours in the mask
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Scale back to pixel coordinates
        px, py = x * block_size, y * block_size
        pw, ph = w * block_size, h * block_size

        # Clamp to image bounds
        pw = min(pw, width - px)
        ph = min(ph, height - py)

        area = pw * ph
        area_ratio = area / page_area

        if area_ratio >= MIN_PHOTO_AREA_RATIO and pw >= MIN_DIMENSION and ph >= MIN_DIMENSION:
            region = img[py:py+ph, px:px+pw]
            variance = float(np.var(region))
            candidates.append((px, py, pw, ph, area, variance))

    return candidates


def _remove_overlaps(
    candidates: list[tuple[int, int, int, int, int, float]],
) -> list[tuple[int, int, int, int, int, float]]:
    """Remove overlapping regions, keeping larger ones."""
    if not candidates:
        return []

    kept = []
    for candidate in candidates:
        x1, y1, w1, h1 = candidate[:4]
        overlaps = False
        for existing in kept:
            x2, y2, w2, h2 = existing[:4]
            # Check overlap
            overlap_x = max(0, min(x1+w1, x2+w2) - max(x1, x2))
            overlap_y = max(0, min(y1+h1, y2+h2) - max(y1, y2))
            overlap_area = overlap_x * overlap_y
            min_area = min(w1*h1, w2*h2)
            if min_area > 0 and overlap_area / min_area > 0.3:
                overlaps = True
                break
        if not overlaps:
            kept.append(candidate)

    return kept


def _extract_background(
    img: np.ndarray,
    slots: list[tuple[int, int, int, int]],
    output_path: Path,
):
    """
    Extract background by inpainting over photo regions.
    Uses OpenCV inpainting to fill photo areas with surrounding background.
    """
    # Create mask of photo regions
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    for x, y, w, h in slots:
        # Slightly shrink the mask to avoid edge artifacts
        margin = 5
        mask[y+margin:y+h-margin, x+margin:x+w-margin] = 255

    # Inpaint using Telea method
    if np.any(mask > 0):
        # For large images, use a smaller inpaint radius
        radius = min(10, max(3, min(img.shape[:2]) // 500))
        background = cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)
    else:
        background = img.copy()

    # Save
    cv2.imwrite(str(output_path), background, [cv2.IMWRITE_JPEG_QUALITY, 95])


def analyze_all_jpeg_templates(
    jpeg_dir: Path,
    output_dir: Path,
) -> list[dict]:
    """Analyze all JPEG album pages in a directory."""
    jpeg_files = sorted(
        [f for f in jpeg_dir.iterdir()
         if f.suffix.lower() in ('.jpg', '.jpeg', '.png')]
    )
    logger.info("Analyzing %d JPEG template pages", len(jpeg_files))

    templates = []
    for i, jpeg_path in enumerate(jpeg_files):
        logger.info("[%d/%d] %s", i+1, len(jpeg_files), jpeg_path.name)
        try:
            result = analyze_jpeg_template(jpeg_path, output_dir)
            templates.append(result)
        except Exception as e:
            logger.error("  FAILED: %s - %s", jpeg_path.name, e)

    logger.info("Analyzed %d/%d templates successfully", len(templates), len(jpeg_files))
    return templates
