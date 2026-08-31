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
