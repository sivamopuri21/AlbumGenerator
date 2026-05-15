"""
Photo-to-Slot Matching Service.

Assigns photos to template slots based on:
1. Orientation matching (portrait photo → portrait slot)
2. Face priority (photos with faces get hero/larger slots)
3. Quality score (best photos in most prominent positions)
"""
import logging
from pathlib import Path
from PIL import Image
from app.models.schemas import PSDSlot, PSDTemplate

logger = logging.getLogger(__name__)


def get_photo_orientation(path: Path) -> str:
    with Image.open(path) as img:
        w, h = img.size
    if w > h * 1.2:
        return "landscape"
    elif h > w * 1.2:
        return "portrait"
    return "square"


def match_photos_to_template(
    photos: list[Path],
    template: PSDTemplate,
    face_counts: dict[str, int] | None = None,
) -> list[tuple[PSDSlot, Path]]:
    """
    Match photos to template slots.
    Returns list of (slot, photo_path) pairs.
    """
    if not template.slots:
        logger.warning("Template %s has no slots", template.filename)
        return []

    slots = template.slots
    available_photos = list(photos[:len(slots)])

    if not available_photos:
        logger.warning("No photos available for template %s", template.filename)
        return []

    # Get orientations for all photos
    photo_info = []
    for p in available_photos:
        orientation = get_photo_orientation(p)
        faces = face_counts.get(p.name, 0) if face_counts else 0
        photo_info.append({"path": p, "orientation": orientation, "faces": faces})

    # Sort slots by size (largest first = hero slots)
    sorted_slots = sorted(slots, key=lambda s: s.width * s.height, reverse=True)

    # Sort photos: more faces first, then by orientation match potential
    photo_info.sort(key=lambda p: p["faces"], reverse=True)

    # Greedy matching: best photo for each slot
    assignments: list[tuple[PSDSlot, Path]] = []
    used_photos: set[int] = set()

    for slot in sorted_slots:
        best_idx = -1
        best_score = -1

        for i, info in enumerate(photo_info):
            if i in used_photos:
                continue
            score = _compute_match_score(slot, info)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0:
            assignments.append((slot, photo_info[best_idx]["path"]))
            used_photos.add(best_idx)
            logger.debug("Matched %s -> slot '%s' (score=%.2f)",
                        photo_info[best_idx]["path"].name, slot.layer_name, best_score)

    logger.info("Matched %d photos to %d slots in template %s",
                len(assignments), len(slots), template.filename)
    return assignments


def _compute_match_score(slot: PSDSlot, photo_info: dict) -> float:
    """Score how well a photo fits a slot."""
    score = 0.0

    # Orientation match bonus
    if slot.orientation == photo_info["orientation"]:
        score += 10.0
    elif slot.orientation == "square" or photo_info["orientation"] == "square":
        score += 5.0  # Square is flexible

    # Face bonus for larger slots (hero positions)
    slot_area = slot.width * slot.height
    if photo_info["faces"] > 0:
        score += photo_info["faces"] * 3.0

    # Slight randomness to avoid always same ordering
    import hashlib
    h = hashlib.md5(str(photo_info["path"]).encode()).hexdigest()
    score += int(h[:4], 16) / 65535.0  # 0-1 random factor

    return score


def distribute_photos_to_pages(
    photos: list[Path],
    templates: list[PSDTemplate],
    total_pages: int,
    face_counts: dict[str, int] | None = None,
) -> list[dict]:
    """
    Distribute all photos across pages.
    Returns list of: {"template": PSDTemplate, "assignments": [(slot, photo), ...]}
    """
    logger.info("Distributing %d photos across %d pages using %d templates",
                len(photos), total_pages, len(templates))

    # Calculate how many photos per page
    total_slots = sum(t.slot_count for t in templates)
    if total_slots == 0:
        logger.error("No slots found in any template")
        return []

    # Cycle templates if fewer than pages needed
    page_templates = []
    for i in range(total_pages):
        page_templates.append(templates[i % len(templates)])

    # Distribute photos evenly across pages
    photo_idx = 0
    pages = []

    for page_num, template in enumerate(page_templates):
        slots_on_page = template.slot_count
        page_photos = photos[photo_idx: photo_idx + slots_on_page]
        photo_idx += slots_on_page

        if not page_photos:
            # No more photos, use what we have
            break

        assignments = match_photos_to_template(page_photos, template, face_counts)
        pages.append({
            "page_num": page_num,
            "template": template,
            "assignments": assignments,
        })
        logger.info("Page %d: template=%s, photos=%d",
                    page_num + 1, template.filename, len(assignments))

    logger.info("Created %d pages total", len(pages))
    return pages
