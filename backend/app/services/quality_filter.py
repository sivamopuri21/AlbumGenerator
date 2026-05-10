import logging
from pathlib import Path
import cv2
import numpy as np

logger = logging.getLogger(__name__)

BLUR_THRESHOLD = 30.0  # Lower = more lenient (was 80)
DARK_THRESHOLD = 20   # Lower = more lenient (was 40)
BRIGHT_THRESHOLD = 250  # Higher = more lenient (was 245)


def compute_blur_score(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return cv2.Laplacian(img, cv2.CV_64F).var()


def compute_brightness(path: Path) -> float:
    img = cv2.imread(str(path))
    if img is None:
        return 128.0
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float(np.mean(hsv[:, :, 2]))


def filter_quality(images: list[Path]) -> list[Path]:
    """Remove blurry and poorly exposed images."""
    logger.info("Quality filter: checking %d images (blur_threshold=%.1f, dark=%.0f, bright=%.0f)",
                len(images), BLUR_THRESHOLD, DARK_THRESHOLD, BRIGHT_THRESHOLD)
    kept: list[Path] = []
    removed_blur = 0
    removed_dark = 0
    removed_bright = 0
    for p in images:
        blur = compute_blur_score(p)
        brightness = compute_brightness(p)
        if blur < BLUR_THRESHOLD:
            logger.info("REMOVED blurry: %s (blur_score=%.1f < %.1f)", p.name, blur, BLUR_THRESHOLD)
            removed_blur += 1
            continue
        if brightness < DARK_THRESHOLD:
            logger.info("REMOVED dark: %s (brightness=%.1f < %.0f)", p.name, brightness, DARK_THRESHOLD)
            removed_dark += 1
            continue
        if brightness > BRIGHT_THRESHOLD:
            logger.info("REMOVED overexposed: %s (brightness=%.1f > %.0f)", p.name, brightness, BRIGHT_THRESHOLD)
            removed_bright += 1
            continue
        logger.debug("KEPT: %s (blur=%.1f, brightness=%.1f)", p.name, blur, brightness)
        kept.append(p)
    logger.info("Quality filter result: %d -> %d images (removed: %d blurry, %d dark, %d overexposed)",
                len(images), len(kept), removed_blur, removed_dark, removed_bright)
    return kept
