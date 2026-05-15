import logging
from pathlib import Path
from app.services.face_service import detect_faces_insightface

logger = logging.getLogger(__name__)


def rank_by_faces(images: list[Path]) -> list[tuple[Path, int]]:
    """Return images sorted by face count descending, with face count."""
    logger.info("Face ranking: analyzing %d images...", len(images))
    results: list[tuple[Path, int]] = []
    for i, p in enumerate(images):
        count = detect_faces_insightface(p)
        results.append((p, count))
        if (i + 1) % 50 == 0:
            logger.info("Face detection progress: %d/%d images", i + 1, len(images))
    results.sort(key=lambda x: x[1], reverse=True)
    faces_found = sum(1 for _, c in results if c > 0)
    logger.info(
        "Face ranking complete: %d images, %d with faces, max faces=%d",
        len(results), faces_found,
        results[0][1] if results else 0,
    )
    return results
