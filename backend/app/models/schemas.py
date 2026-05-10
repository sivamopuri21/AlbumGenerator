from pydantic import BaseModel
from typing import Optional
from enum import Enum


class BookSize(str, Enum):
    SIZE_12X36 = "12x36"
    SIZE_18X24 = "18x24"
    SIZE_18X26 = "18x26"


BOOK_DIMENSIONS = {
    BookSize.SIZE_12X36: (12, 36),  # width x height in inches
    BookSize.SIZE_18X24: (18, 24),
    BookSize.SIZE_18X26: (18, 26),
}


class JobStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PREPROCESSING = "preprocessing"
    DEDUPLICATING = "deduplicating"
    FILTERING = "filtering"
    DETECTING_FACES = "detecting_faces"
    PARSING_TEMPLATES = "parsing_templates"
    ASSIGNING_PHOTOS = "assigning_photos"
    RENDERING = "rendering"
    EXPORTING = "exporting"
    COMPLETED = "completed"
    FAILED = "failed"


class JobProgress(BaseModel):
    job_id: str
    status: JobStatus
    progress: float = 0.0
    message: str = ""
    book_size: str = ""
    total_sheets: int = 0
    total_pages: int = 0
    total_images: int = 0
    processed_images: int = 0
    error: Optional[str] = None


class PSDSlot(BaseModel):
    """A photo slot extracted from a PSD template."""
    layer_name: str
    x: int
    y: int
    width: int
    height: int
    orientation: str = "landscape"  # landscape, portrait, square


class PSDTemplate(BaseModel):
    """Parsed PSD template with background and slots."""
    filename: str
    width: int
    height: int
    slots: list[PSDSlot]
    background_path: str  # path to extracted background image
    slot_count: int = 0


class AlbumConfig(BaseModel):
    """User configuration for album generation."""
    book_size: BookSize
    num_sheets: int
    # Computed
    total_pages: int = 0
    width_inches: float = 0
    height_inches: float = 0
    width_px: int = 0
    height_px: int = 0
    dpi: int = 300
