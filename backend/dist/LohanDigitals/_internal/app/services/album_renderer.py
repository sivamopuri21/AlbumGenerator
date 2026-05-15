import logging
import shutil
from pathlib import Path
from PIL import Image
from app.models.schemas import LayoutTemplate

logger = logging.getLogger(__name__)

PAGE_WIDTH_MM = 297
PAGE_HEIGHT_MM = 210
GAP_PCT = 1.5


def render_album_html(
    pages: list[dict],
    output_dir: Path,
) -> Path:
    """
    Generate a single HTML file with all album pages.
    Each page dict: {"template": LayoutTemplate, "images": [Path, ...]}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    img_dir = output_dir / "images"
    img_dir.mkdir(exist_ok=True)
    logger.info("Rendering album: %d pages to %s", len(pages), output_dir)

    html_parts = [_html_head()]

    for page_idx, page in enumerate(pages):
        template: LayoutTemplate = page["template"]
        images: list[Path] = page["images"]
        slots = template.slots

        html_parts.append(f'<div class="page" id="page-{page_idx}">')
        logger.info("Rendering page %d/%d: template=%s, images=%d",
                     page_idx + 1, len(pages), template.layout_id, len(images))
        for slot_idx, slot in enumerate(slots):
            if slot_idx >= len(images):
                break
            img_path = images[slot_idx]
            dest = img_dir / f"p{page_idx}_s{slot_idx}{img_path.suffix}"
            shutil.copy2(img_path, dest)
            rel = f"images/{dest.name}"

            html_parts.append(
                f'  <div class="slot" style="'
                f"left:{slot.x}%;top:{slot.y}%;"
                f"width:{slot.w}%;height:{slot.h}%;"
                f'">'
                f'<img src="{rel}" alt="Album photo" />'
                f"</div>"
            )
        html_parts.append("</div>")

    html_parts.append("</body></html>")
    html_file = output_dir / "album.html"
    html_file.write_text("\n".join(html_parts), encoding="utf-8")
    logger.info("Rendered %d pages to %s", len(pages), html_file)
    return html_file


def _html_head() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Album</title>
<style>
  @page { size: 297mm 210mm; margin: 0; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #f5f5f5; }
  .page {
    position: relative;
    width: 297mm; height: 210mm;
    background: #fff;
    overflow: hidden;
    page-break-after: always;
    margin: 10px auto;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }
  .slot {
    position: absolute;
    overflow: hidden;
    padding: 2mm;
  }
  .slot img {
    width: 100%; height: 100%;
    object-fit: cover;
    border-radius: 2px;
  }
  @media print {
    body { background: #fff; }
    .page { box-shadow: none; margin: 0; }
  }
</style>
</head>
<body>"""
