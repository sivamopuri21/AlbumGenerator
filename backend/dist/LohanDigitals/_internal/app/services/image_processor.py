import logging
from pathlib import Path
from PIL import Image
import cv2
import numpy as np

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
TARGET_MAX_DIM = 2400
BLUR_THRESHOLD = 80.0


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_FORMATS


def preprocess_images(image_dir: Path) -> list[Path]:
    """Resize, normalize format, remove corrupted files."""
    all_files = sorted(image_dir.iterdir())
    logger.info("Preprocessing: found %d files in %s", len(all_files), image_dir)
    valid: list[Path] = []
    skipped = 0
    for p in all_files:
        if not is_supported_image(p):
            logger.debug("Skipping non-image file: %s", p.name)
            skipped += 1
            continue
        try:
            img = Image.open(p)
            img.verify()
            img = Image.open(p)
            img = img.convert("RGB")
            w, h = img.size
            resized = False
            if max(w, h) > TARGET_MAX_DIM:
                ratio = TARGET_MAX_DIM / max(w, h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                logger.debug("Resized %s: %dx%d -> %dx%d", p.name, w, h, new_w, new_h)
                resized = True
            out = p.with_suffix(".jpg")
            img.save(out, "JPEG", quality=92)
            if out != p:
                p.unlink(missing_ok=True)
            valid.append(out)
            logger.debug("Preprocessed: %s (%dx%d%s)", out.name, img.size[0], img.size[1], " resized" if resized else "")
        except Exception as e:
            logger.warning("Skipping corrupted image %s: %s", p.name, e)
            p.unlink(missing_ok=True)
    logger.info("Preprocessing complete: %d valid, %d skipped, %d corrupted out of %d files",
                len(valid), skipped, len(all_files) - len(valid) - skipped, len(all_files))
    return valid
