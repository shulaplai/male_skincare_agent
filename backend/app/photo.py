"""Photo storage: compress + persist to the local filesystem.

Local-first contract: photos stay on the user's machine by default. We compress
aggressively (max 1024px, JPEG q78) before writing, mirroring the SKINFILE quota
lesson but now on the backend.
"""
from io import BytesIO
from pathlib import Path

from PIL import Image

from .config import settings

MAX_DIM = 1024
QUALITY = 78


def compress_image(data: bytes, max_dim: int = MAX_DIM, quality: int = QUALITY) -> bytes:
    img = Image.open(BytesIO(data))
    img = img.convert("RGB")
    img.thumbnail((max_dim, max_dim))
    out = BytesIO()
    img.save(out, "JPEG", quality=quality)
    return out.getvalue()


def save_photo(photo_id: str, data: bytes) -> str:
    """Persist a photo and return its path relative to the data dir."""
    compressed = compress_image(data)
    photos_dir = Path(settings.data_dir) / "photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    path = photos_dir / f"{photo_id}.jpg"
    path.write_bytes(compressed)
    return str(path.relative_to(settings.data_dir))
