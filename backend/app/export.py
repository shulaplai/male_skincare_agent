"""Data export/import — the local-first "keep it on your own machine" guarantee.

Export bundles the entire data dir (SQLite + photos) into a single zip, so a user
can back up / move their whole record off-cloud. Import restores it, with a path
traversal guard.
"""
import io
import zipfile
from pathlib import Path

from .config import settings


def export_zip() -> bytes:
    data_dir = Path(settings.data_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if data_dir.exists():
            for p in sorted(data_dir.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(data_dir))
    return buf.getvalue()


def import_zip(data: bytes) -> None:
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    root = data_dir.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            target = (data_dir / name).resolve()
            if not str(target).startswith(str(root) + "/") and target != root:
                raise ValueError(f"unsafe path in archive: {name}")
        zf.extractall(data_dir)
