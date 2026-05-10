"""
Image deduplication using perceptual hashing (no CLIP dependency).
Avoids transformers library bugs with newer versions.
"""
import logging
from pathlib import Path
import numpy as np
from PIL import Image
import cv2

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 10  # Hamming distance threshold (lower = more similar)


def _phash(image_path: Path, hash_size: int = 8) -> np.ndarray:
    """Compute perceptual hash of an image."""
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return np.zeros(hash_size * hash_size, dtype=np.uint8)
    resized = cv2.resize(img, (hash_size * 2, hash_size * 2), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    dct_low = dct[:hash_size, :hash_size]
    median = np.median(dct_low)
    return (dct_low > median).flatten().astype(np.uint8)


def _hamming_distance(h1: np.ndarray, h2: np.ndarray) -> int:
    return int(np.sum(h1 != h2))


def deduplicate_images(images: list[Path]) -> list[Path]:
    """Remove near-duplicate images using perceptual hashing."""
    if len(images) <= 1:
        return images

    logger.info("Computing hashes for %d images...", len(images))
    hashes = [_phash(p) for p in images]
    keep_mask = [True] * len(images)

    for i in range(len(images)):
        if not keep_mask[i]:
            continue
        for j in range(i + 1, len(images)):
            if not keep_mask[j]:
                continue
            dist = _hamming_distance(hashes[i], hashes[j])
            if dist <= SIMILARITY_THRESHOLD:
                keep_mask[j] = False
                logger.info(
                    "Duplicate: %s ~ %s (dist=%d)",
                    images[i].name, images[j].name, dist,
                )

    kept = [img for img, k in zip(images, keep_mask) if k]
    logger.info("Deduplication: %d -> %d images", len(images), len(kept))
    return kept
