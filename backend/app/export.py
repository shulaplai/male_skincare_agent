"""Data export/import — the local-first "keep it on your own machine" guarantee.

Export bundles the user's own record (SQLite + photos + uploaded clips) into a single
zip, so they can back up / move their whole record off-cloud. Import restores it, with
a path traversal guard.

⚠️ **The archive must contain user data, not build artefacts.** `data_dir` is also where
the embedder caches its ONNX model (`SKINCOACH_EMBEDDER_CACHE_DIR=./data/.fastembed-cache`,
plus the `.hf-cache` HuggingFace mirror of the same model). `rglob` used to sweep those in:
measured on the real dev data dir the archive was **1070 MB, of which 962 MB (90 %) was the
same 235 MB model blob stored twice** — ONNX weights deflate at ~0.92 ratio, so building it
cost ~50 s of CPU and the finished zip was held on the heap (twice, via `getvalue()`), which
is why `GET /api/export` returned **0 bytes in 45 s** and the UI's「匯出數據」button just sat
there. The real user data was ~72 MB. `EXPORT_SKIP_DIRS` fixes that; `iter_export_zip` streams
the result so peak memory stays flat instead of holding the whole archive in RAM.
"""
import io
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path

from .config import settings

#: Directory names (at any depth) that hold caches / build output, never user data.
#: `.fastembed-cache` + `.hf-cache` are the embedder model; `__pycache__` shows up when
#: someone runs a module from inside the data dir. Keep this list short and boring.
EXPORT_SKIP_DIRS = frozenset({".fastembed-cache", ".hf-cache", "__pycache__", ".cache"})


def _included_files(data_dir: Path) -> list[Path]:
    """Every file under `data_dir` that belongs in an export, sorted and deterministic."""
    if not data_dir.exists():
        return []
    out = []
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file():
            continue
        if EXPORT_SKIP_DIRS.intersection(p.relative_to(data_dir).parts):
            continue
        out.append(p)
    return out


def _write_members(zf: zipfile.ZipFile, data_dir: Path) -> None:
    for p in _included_files(data_dir):
        zf.write(p, p.relative_to(data_dir))


def iter_export_zip(chunk_size: int = 1 << 20) -> Iterator[bytes]:
    """Yield the export zip in `chunk_size` chunks, built in a temp file.

    Used by the route so a backup of a multi-hundred-MB data dir does not sit in RAM.
    The temp file is cleaned up when the generator finishes (or the client disconnects,
    because Starlette closes the generator).
    """
    data_dir = Path(settings.data_dir)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "skincoach.zip"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            _write_members(zf, data_dir)
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk


def export_zip() -> bytes:
    """The whole export as bytes. Kept for tests and in-process callers."""
    data_dir = Path(settings.data_dir)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        _write_members(zf, data_dir)
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
