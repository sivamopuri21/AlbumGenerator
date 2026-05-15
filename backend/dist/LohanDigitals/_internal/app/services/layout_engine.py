import json
import logging
from pathlib import Path
from PIL import Image
from app.models.schemas import LayoutTemplate, LayoutSlot

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def load_templates() -> list[LayoutTemplate]:
    templates_file = TEMPLATES_DIR / "layouts.json"
    with open(templates_file) as f:
        data = json.load(f)
    templates = [LayoutTemplate(**t) for t in data["templates"]]
    logger.info("Loaded %d layout templates from %s", len(templates), templates_file)
    return templates


def get_image_orientation(path: Path) -> str:
    img = Image.open(path)
    w, h = img.size
    if w > h * 1.2:
        return "landscape"
    elif h > w * 1.2:
        return "portrait"
    return "square"


def rule_based_select(
    image_count: int,
    orientations: list[str],
    templates: list[LayoutTemplate],
) -> list[LayoutTemplate]:
    """Filter templates that can hold the given image count."""
    candidates = [
        t for t in templates
        if t.min_images <= image_count <= t.max_images
    ]
    if not candidates:
        candidates = [
            t for t in templates if t.max_images >= image_count
        ]
    if not candidates:
        candidates = sorted(templates, key=lambda t: t.max_images, reverse=True)[:3]

    landscape_ratio = orientations.count("landscape") / max(len(orientations), 1)
    portrait_ratio = orientations.count("portrait") / max(len(orientations), 1)

    def score(t: LayoutTemplate) -> float:
        s = 0.0
        if "landscape" in t.best_for and landscape_ratio > 0.5:
            s += 2
        if "portrait" in t.best_for and portrait_ratio > 0.5:
            s += 2
        if "mixed" in t.best_for and 0.3 < landscape_ratio < 0.7:
            s += 1
        return s

    candidates.sort(key=score, reverse=True)
    result = candidates[:5]
    logger.info("Rule-based select: %d images, orientations=%s -> %d candidates: %s",
                image_count, orientations, len(result), [t.layout_id for t in result])
    return result
