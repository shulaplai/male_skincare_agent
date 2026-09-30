import io
import zipfile

from app.export import export_zip, import_zip


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
