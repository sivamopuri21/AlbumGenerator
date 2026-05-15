from pathlib import Path
from PIL import Image


def get_image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def is_landscape(path: Path) -> bool:
    w, h = get_image_dimensions(path)
    return w > h


def is_portrait(path: Path) -> bool:
    w, h = get_image_dimensions(path)
    return h > w


def human_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
