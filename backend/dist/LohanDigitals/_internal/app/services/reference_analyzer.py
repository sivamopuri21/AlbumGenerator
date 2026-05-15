import logging
from pathlib import Path
from PIL import Image
from PyPDF2 import PdfReader
from pdf2image import convert_from_path
from app.services.openai_service import analyze_reference_layout

logger = logging.getLogger(__name__)


def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> list[Path]:
    """Convert PDF pages to images."""
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        pages = convert_from_path(str(pdf_path), dpi=150)
        paths = []
        for i, page in enumerate(pages):
            out = output_dir / f"ref_page_{i:03d}.jpg"
            page.save(out, "JPEG", quality=90)
            paths.append(out)
        logger.info("Extracted %d pages from PDF", len(paths))
        return paths
    except Exception as e:
        logger.error("PDF extraction failed: %s", e)
        return []


def analyze_reference(ref_images: list[Path]) -> dict:
    """Analyze reference album layout using OpenAI Vision."""
    if not ref_images:
        return _default_analysis()
    try:
        analysis = analyze_reference_layout(ref_images)
        logger.info("Reference analysis: %s", analysis.get("overall_style", "unknown"))
        return analysis
    except Exception as e:
        logger.warning("OpenAI analysis failed, using defaults: %s", e)
        return _default_analysis()


def _default_analysis() -> dict:
    return {
        "pages": [],
        "overall_style": "classic",
        "avg_images_per_page": 3.0,
    }
