import base64
import json
import logging
import time
from pathlib import Path
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 2


def _client() -> OpenAI:
    return OpenAI(api_key=settings.openai_api_key)


def _retry(fn, *args, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = fn(*args, **kwargs)
            logger.info("OpenAI call succeeded on attempt %d", attempt)
            return result
        except Exception as e:
            logger.warning("OpenAI attempt %d/%d failed: %s", attempt, MAX_RETRIES, e)
            if attempt == MAX_RETRIES:
                logger.error("OpenAI call failed after %d attempts: %s", MAX_RETRIES, e)
                raise
            time.sleep(RETRY_DELAY * attempt)


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def analyze_reference_layout(ref_images: list[Path]) -> dict:
    """Use Vision API to analyze reference album layout patterns."""
    logger.info("Analyzing reference layout with %d images via OpenAI Vision", len(ref_images))
    client = _client()
    sample = ref_images[:5]
    content = [
        {
            "type": "text",
            "text": (
                "Analyze these album pages. For each page describe:\n"
                "1. Number of images\n"
                "2. Layout type (grid, collage, single, mixed)\n"
                "3. Dominant color tone\n"
                "4. Overall style\n"
                "Return JSON: {\"pages\": [{\"image_count\": int, "
                "\"layout_type\": str, \"color_tone\": str, \"style\": str}], "
                "\"overall_style\": str, \"avg_images_per_page\": float}"
            ),
        }
    ]
    for img_path in sample:
        b64 = _encode_image(img_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
        })

    def _call():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    return _retry(_call)


def generate_story_flow(
    image_count: int,
    face_counts: list[int],
    has_groups: bool,
) -> dict:
    """Generate album story structure using LLM."""
    logger.info("Generating story flow: %d images, %d with faces, groups=%s",
                image_count, sum(1 for f in face_counts if f > 0), has_groups)
    client = _client()
    prompt = (
        f"I have {image_count} photos for an album. "
        f"Face distribution: max faces in a photo = {max(face_counts) if face_counts else 0}, "
        f"photos with faces = {sum(1 for f in face_counts if f > 0)}. "
        f"Group photos present: {has_groups}.\n\n"
        "Create an album flow with sections. Return JSON:\n"
        '{"sections": [{"name": str, "description": str, '
        '"suggested_image_count": int, "priority": "high"|"medium"|"low"}], '
        '"total_pages": int, "images_per_page_avg": float}'
    )

    def _call():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    return _retry(_call)


def select_layout_for_page(
    image_count: int,
    orientations: list[str],
    section_name: str,
    available_layouts: list[str],
) -> str:
    """Ask LLM to pick the best layout template for a page."""
    logger.info("Selecting layout: section=%s, images=%d, orientations=%s, candidates=%s",
                section_name, image_count, orientations, available_layouts)
    client = _client()
    prompt = (
        f"Section: {section_name}\n"
        f"Images on this page: {image_count}\n"
        f"Orientations: {orientations}\n"
        f"Available layout IDs: {available_layouts}\n\n"
        "Pick the single best layout_id. Return JSON: "
        '{"layout_id": str, "reason": str}'
    )

    def _call():
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    return _retry(_call)
