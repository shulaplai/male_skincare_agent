import io
import zipfile

from app.export import EXPORT_SKIP_DIRS, export_zip, import_zip, iter_export_zip


def test_export_import_roundtrip(tmp_path, monkeypatch):
    # Point the data dir at a temp path so the test is isolated.
    monkeypatch.setattr("app.export.settings.data_dir", str(tmp_path))
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.jpg").write_bytes(b"photo-bytes")
    (tmp_path / "skincoach.db").write_bytes(b"fake-db")

    blob = export_zip()
    assert zipfile.is_zipfile(io.BytesIO(blob))

    # Wipe and restore.
    for p in tmp_path.iterdir():
        if p.is_file():
            p.unlink()
    import_zip(blob)

    assert (tmp_path / "photos" / "a.jpg").read_bytes() == b"photo-bytes"
    assert (tmp_path / "skincoach.db").read_bytes() == b"fake-db"


def test_export_includes_stored_clips(tmp_path, monkeypatch):
    """`docs/backend-flow.md` used to claim the export zip leaves clips out. It never did.

    `export_zip` walks the whole data dir with `rglob`, so `videos/` was always in the
    archive. Pinned here because the local-first promise ("you can take your data with
    you") is only as good as its weakest file, and the docs said otherwise.
    """
    monkeypatch.setattr("app.export.settings.data_dir", str(tmp_path))
    vid = "a" * 32
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / f"{vid}.mp4").write_bytes(b"clip-bytes")

    names = zipfile.ZipFile(io.BytesIO(export_zip())).namelist()
    assert f"videos/{vid}.mp4" in names


def test_import_rejects_path_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.export.settings.data_dir", str(tmp_path))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", "x")

    try:
        import_zip(buf.getvalue())
        assert False, "should have raised"
    except ValueError as e:
        assert "unsafe path" in str(e)


def test_export_skips_embedder_caches(tmp_path, monkeypatch):
    """The embedder model lives under `data/` and must NOT be in a user's backup.

    Regression: measured on the real dev data dir, `rglob` swept in `.hf-cache` (481 MB)
    and `.fastembed-cache` (481 MB) — the same 235 MB ONNX blob twice — so the archive was
    1070 MB (90 % model) instead of ~72 MB of actual user data, and deflating it took ~50 s
    of CPU before a single byte reached the client. `GET /api/export` timed out at 0 bytes.

    The old tests never caught this because they point `data_dir` at a clean `tmp_path`.
    This one plants the caches on purpose, shaped like the real thing (nested dirs).
    """
    monkeypatch.setattr("app.export.settings.data_dir", str(tmp_path))
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.jpg").write_bytes(b"photo-bytes")
    (tmp_path / "skincoach.db").write_bytes(b"fake-db")
    for cache in (".hf-cache", ".fastembed-cache"):
        blob = tmp_path / cache / "models--x" / "blobs"
        blob.mkdir(parents=True)
        (blob / "model.onnx").write_bytes(b"x" * 4096)

    names = zipfile.ZipFile(io.BytesIO(export_zip())).namelist()
    assert "photos/a.jpg" in names
    assert "skincoach.db" in names
    assert not [n for n in names if n.split("/")[0] in EXPORT_SKIP_DIRS], names


def test_iter_export_zip_streams_the_same_archive(tmp_path, monkeypatch):
    """The route streams now; it must still produce a readable, identical archive."""
    monkeypatch.setattr("app.export.settings.data_dir", str(tmp_path))
    (tmp_path / "photos").mkdir()
    (tmp_path / "photos" / "a.jpg").write_bytes(b"photo-bytes")

    chunks = list(iter_export_zip(chunk_size=8))
    assert len(chunks) > 1, "must actually chunk, not return one blob"
    assert all(len(c) <= 8 for c in chunks)

    assert zipfile.ZipFile(io.BytesIO(b"".join(chunks))).namelist() == ["photos/a.jpg"]
    assert zipfile.ZipFile(io.BytesIO(export_zip())).namelist() == ["photos/a.jpg"]

