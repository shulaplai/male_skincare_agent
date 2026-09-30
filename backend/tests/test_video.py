"""Video → frames.

`imageio`'s ffmpeg plugin cannot read a `BytesIO` (it spawns ffmpeg as a subprocess),
so both the product code and these tests work with real files. Helper below builds a
tiny synthetic clip with a block that moves across the frame — enough to exercise
sampling and de-duplication without shipping a fixture binary.
"""
import datetime
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.video import (
    COMPRESS_OVER_BYTES,
    MAX_FRAMES,
    MAX_SECONDS,
    VideoCompressError,
    VideoDecodeError,
    VideoTooLarge,
    VideoTooLong,
    check_size,
    compress_video,
    delete_video,
    extract_frames,
    probe,
    save_video,
    video_file,
    video_path,
)


def make_video(seconds: float = 3.0, fps: int = 10, *, moving: bool = True) -> str:
    """A real (tiny) mp4 on disk. Returns its path; caller removes it."""
    imageio = pytest.importorskip("imageio.v2")
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    writer = imageio.get_writer(path, format="ffmpeg", fps=fps, codec="libx264", macro_block_size=1)
    n = max(int(seconds * fps), 1)
    for i in range(n):
        frame = np.full((120, 160, 3), 200, np.uint8)
        x = int((i / max(n - 1, 1)) * (140 if moving else 0))
        frame[40:80, 10 + x : 50 + x] = 40
        writer.append_data(frame)
    writer.close()
    return path


@pytest.fixture
def clip():
    path = make_video()
    yield path
    if os.path.exists(path):
        os.unlink(path)


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def test_extracts_at_most_the_frame_cap(clip):
    ex = extract_frames(clip)
    assert 1 <= ex.n_frames <= MAX_FRAMES
    assert len(ex.timestamps) == ex.n_frames
    assert all(isinstance(f, bytes) and f[:2] == b"\xff\xd8" for f in ex.frames), "must be JPEG"


def test_frames_are_spread_across_the_whole_clip(clip):
    """Found by testing: taking the first N survivors biased everything to the start.

    A 3 s clip returned frames from 0.0–1.3 s, which is wrong for the actual use case —
    the user pans the camera, so later frames are different parts of the face.
    """
    ex = extract_frames(clip)
    assert ex.n_frames >= 2
    assert ex.timestamps[0] < 0.5, "should start near the beginning"
    assert ex.timestamps[-1] > ex.duration * 0.6, "should reach into the second half"


def test_a_static_clip_still_returns_a_frame():
    """De-duplication must never leave a valid video with nothing."""
    path = make_video(seconds=2.0, fps=10, moving=False)
    try:
        ex = extract_frames(path)
        assert ex.n_frames >= 1
        assert ex.frames[0][:2] == b"\xff\xd8"
    finally:
        os.unlink(path)


def test_probe_reports_metadata_without_decoding(clip):
    meta = probe(clip)
    assert meta.duration > 0
    assert meta.fps > 0
    assert (meta.width, meta.height) == (160, 120)
    assert meta.frames == [], "probe must not decode frames"


# ---------------------------------------------------------------------------
# Caps and failures
# ---------------------------------------------------------------------------


def test_duration_cap():
    path = make_video(seconds=MAX_SECONDS + 2, fps=2, moving=False)
    try:
        with pytest.raises(VideoTooLong) as e:
            extract_frames(path)
        assert f"{MAX_SECONDS:.0f}" in str(e.value)
    finally:
        os.unlink(path)


def test_garbage_input_raises_a_typed_error_not_a_crash():
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.write(fd, b"\x00" * 5000)
    os.close(fd)
    try:
        with pytest.raises(VideoDecodeError):
            extract_frames(path)
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def test_save_and_locate_a_clip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    vid = "a" * 32
    rel = save_video(vid, b"fake-bytes", ".mov")
    assert rel == f"videos/{vid}.mov"
    assert (tmp_path / rel).read_bytes() == b"fake-bytes"
    assert video_file(vid) == tmp_path / rel
    assert delete_video(vid) is True
    assert video_file(vid) is None


def test_unknown_suffix_falls_back_to_mp4(tmp_path, monkeypatch):
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    vid = "b" * 32
    assert save_video(vid, b"x", ".exe").endswith(f"{vid}.mp4")


def test_video_file_rejects_a_bad_id_shape(tmp_path, monkeypatch):
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    assert video_file("../../etc/passwd") is None
    assert video_file("nothex") is None


# ---------------------------------------------------------------------------
# POST /api/videos
# ---------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient with BOTH the data dir and the database redirected.

    The database override is not optional: `POST /api/videos` now records a `Video` row,
    so without it these tests would write to the user's real `backend/data/skincoach.db`.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.config import settings
    from app.db import Base, get_session
    from app.main import app
    from app.models import Conversation, User

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)

    def override():
        db = sf()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_session] = override
    session = sf()
    user = User(name="阿軒")
    session.add(user)
    session.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚")
    session.add(conv)
    session.commit()
    cid = conv.id
    session.close()

    yield TestClient(app), tmp_path, cid, sf
    app.dependency_overrides.pop(get_session, None)


def post_video_to(client, path, cid, name="clip.mp4"):
    with open(path, "rb") as fh:
        return client.post(
            f"/api/videos?cid={cid}", files={"file": (name, fh, "video/mp4")}
        )


def test_upload_returns_frames_that_the_vision_path_can_read(api):
    """The whole point: frames must be ordinary photos, usable by the existing path."""
    from app.photo import load_photo_b64, photo_exists

    client, data_dir, cid, _ = api
    path = make_video()
    try:
        r = post_video_to(client, path, cid)
    finally:
        os.unlink(path)

    assert r.status_code == 200
    body = r.json()
    assert body["duration"] > 0
    assert 1 <= len(body["frames"]) <= MAX_FRAMES
    assert body["sampled"] >= len(body["frames"])

    for fr in body["frames"]:
        assert photo_exists(fr["id"]), f"{fr['id']} is not a stored photo"
        b64 = load_photo_b64(fr["id"])
        assert b64 is not None and b64["media_type"] == "image/jpeg"
        assert len(b64["data"]) > 100

    # The clip itself is kept locally.
    assert (data_dir / body["path"]).exists()


def test_upload_rejects_an_over_long_clip_and_keeps_nothing(api):
    client, data_dir, cid, _ = api
    path = make_video(seconds=MAX_SECONDS + 2, fps=2, moving=False)
    try:
        r = post_video_to(client, path, cid)
    finally:
        os.unlink(path)

    assert r.status_code == 422
    assert "秒" in r.json()["detail"]
    # A clip we cannot use must not be left on disk.
    videos = list((data_dir / "videos").glob("*")) if (data_dir / "videos").exists() else []
    assert videos == [], f"unusable clip kept: {videos}"


def test_upload_rejects_garbage(api):
    client, _dd, cid, _ = api
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.write(fd, b"\x00" * 5000)
    os.close(fd)
    try:
        r = post_video_to(client, path, cid)
    finally:
        os.unlink(path)
    assert r.status_code == 422


def test_uploaded_frames_drive_a_consult_that_writes_the_entry(api, monkeypatch):
    """End-to-end: clip → frames → consult. The frames are what the agent looks at."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.agent.graph import build_graph
    from app.agent.schemas import Advice, SkinAnalysis
    from app.db import Base
    from app.models import Conversation, Entry, Photo, User
    from app.rag import DeterministicEmbedder

    client, _dd, cid, _ = api
    path = make_video()
    try:
        frames = post_video_to(client, path, cid).json()["frames"]
    finally:
        os.unlink(path)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    s.add(c)
    s.commit()
    cid = c.id
    s.close()

    class VideoLLM:
        def structured(self, system, user, schema):
            if schema is SkinAnalysis:
                return SkinAnalysis(
                    observes_skin=True,
                    summary="睇咗片",
                    attributes=[{"key": "acne", "severity": 2, "note": ""}],
                )
            return Advice(reply="好。", items=["a"], disclaimer="d", escalate=False)

    g = build_graph(llm=VideoLLM(), session_factory=sf, embedder=DeterministicEmbedder())
    res = g.invoke(
        {
            "conversation_id": cid,
            "user_text": "拍咗條片俾你睇",
            "photo_paths": [f["id"] for f in frames],
            "cloud_analysis": False,
            "trace": [],
        }
    )

    s = sf()
    entry = s.query(Entry).filter_by(conversation_id=cid).first()
    assert entry is not None
    assert s.query(Photo).count() == len(frames), "every kept frame attaches to the day"
    s.close()
    assert res["analysis"]["observes_skin"] is True


# ---------------------------------------------------------------------------
# Compression instead of a size limit
# ---------------------------------------------------------------------------


def test_small_clip_is_left_alone(tmp_path, monkeypatch):
    """Ordinary phone footage must not be re-encoded: 20 s of 1080p is ~30 MB."""
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    path = make_video(seconds=1.0, fps=5)
    try:
        same, before, after = compress_video(path)
        assert same == Path(path)
        assert before == after
        assert Path(path).exists(), "the original must not be touched"
    finally:
        os.unlink(path)


def test_oversized_clip_is_re_encoded_smaller_with_no_audio(tmp_path, monkeypatch):
    """Above the threshold it shrinks, the original goes away, and audio is dropped.

    Audio is never analysed, so keeping it would mean storing a recording of the user's
    voice for no purpose.
    """
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    monkeypatch.setattr("app.video.COMPRESS_OVER_BYTES", 1024)  # force the path

    # A real clip lives at data/videos/<32hex>.mp4, so build it there — `video_file`
    # resolves ids inside the data dir and would never see a file from `mkstemp`.
    vid = "a" * 32
    vdir = tmp_path / "videos"
    vdir.mkdir()
    path = str(vdir / f"{vid}.mp4")
    imageio = pytest.importorskip("imageio.v2")
    w = imageio.get_writer(path, format="ffmpeg", fps=10, codec="libx264", macro_block_size=1)
    rng = np.random.default_rng(0)
    for i in range(30):
        w.append_data(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8))  # noisy → big
    w.close()

    out, before, after = compress_video(path)
    try:
        assert after < before, f"expected a smaller file: {before} → {after}"
        assert out != Path(path)
        assert out.exists()
        assert not Path(path).exists(), "the original is replaced, not duplicated"
        assert out.stat().st_size == after

        assert out.name == f"{vid}.c.mp4"

        import subprocess

        from app.video import _ffmpeg_exe

        streams = subprocess.run(
            [_ffmpeg_exe(), "-hide_banner", "-i", str(out)],
            capture_output=True,
        ).stderr.decode(errors="replace")
        assert "Audio:" not in streams, "audio must be dropped"
        assert "Video:" in streams

        # Re-encoding moved the clip to `<id>.c<ext>`. An earlier `video_file` only
        # looked for `<id>.<ext>`, so a compressed clip was invisible: `video_file`
        # returned None, and `delete_video` reported nothing to remove — the clip
        # would have outlived deletion of its own conversation.
        assert video_file(vid) == out, "a compressed clip must still be findable by id"
        assert delete_video(vid) is True
        assert not out.exists()
    finally:
        out.unlink(missing_ok=True)


def test_video_path_does_not_write_anything(tmp_path, monkeypatch):
    monkeypatch.setattr("app.video.settings.data_dir", str(tmp_path))
    vid = "c" * 32
    p = video_path(vid, ".mov")
    assert p == tmp_path / "videos" / f"{vid}.mov"
    assert not p.exists(), "computing the path must not create the file"
    assert not (tmp_path / "videos").exists()


# ---------------------------------------------------------------------------
# 100 MB ceiling (user decision, reinstated)
# ---------------------------------------------------------------------------


def test_there_is_a_100mb_ceiling():
    """The number is arithmetic, not a quoted "typical size": 100 MB / 20 s = 40 Mbps.

    The message names the limit and the likely cause (4K / high frame rate) rather than
    asserting a "typical MB" figure this project has not measured.
    """
    from app.video import MAX_BYTES, check_size

    assert MAX_BYTES == 100 * 1024 * 1024
    check_size(MAX_BYTES)  # exactly at the limit is allowed
    with pytest.raises(VideoTooLarge) as e:
        check_size(MAX_BYTES + 1)
    msg = str(e.value)
    assert "100 MB" in msg
    assert "40 Mbps" in msg, "should justify the number rather than quote a typical size"
    assert "1080p" in msg, "should tell the user what to do"


def test_compression_threshold_sits_below_the_ceiling():
    from app.video import COMPRESS_OVER_BYTES, MAX_BYTES

    assert COMPRESS_OVER_BYTES < MAX_BYTES, (
        "anything accepted but large should be shrunk before it is kept"
    )


def test_upload_over_the_ceiling_is_refused_and_writes_nothing(api):
    """Refused while streaming, so nothing oversized is left in the data dir."""
    client, data_dir, cid, _ = api
    oversized = b"\x00" * (100 * 1024 * 1024 + 2 * 1024 * 1024)

    r = client.post(f"/api/videos?cid={cid}", files={"file": ("big.mp4", oversized, "video/mp4")})

    assert r.status_code == 413
    assert "100 MB" in r.json()["detail"]
    videos = list((data_dir / "videos").glob("*")) if (data_dir / "videos").exists() else []
    assert videos == [], f"oversized upload must not be left on disk: {videos}"


# ---------------------------------------------------------------------------
# The clip is a row, and "permanently delete" must really delete
# ---------------------------------------------------------------------------


def test_upload_records_a_video_row(api):
    """Without the row the clip is an orphan file nothing can find or delete."""
    from app.models import Video

    client, data_dir, cid, sf = api
    path = make_video()
    try:
        body = post_video_to(client, path, cid).json()
    finally:
        os.unlink(path)

    s = sf()
    row = s.query(Video).filter_by(id=body["video_id"]).first()
    assert row is not None
    assert row.conversation_id == cid
    assert row.path == body["path"]
    assert row.duration > 0
    assert row.frames == [f["id"] for f in body["frames"]], "frames are recorded too"
    s.close()
    assert (data_dir / body["path"]).exists()


def test_upload_rejects_an_unknown_conversation(api):
    client, data_dir, _cid, _sf = api
    path = make_video()
    try:
        r = post_video_to(client, path, "0" * 32)
    finally:
        os.unlink(path)
    assert r.status_code == 404
    # A clip with nowhere to belong must not be kept.
    videos = list((data_dir / "videos").glob("*")) if (data_dir / "videos").exists() else []
    assert videos == []


def test_deleting_a_conversation_removes_the_files_from_disk(api):
    """Measured before the fix: deleting a conversation left every photo on disk.

    The route says "permanently delete a conversation and all its records" and a DB
    cascade never touches the filesystem — so the files stayed, silently. Clips would
    have gone the same way.
    """
    import io

    from PIL import Image

    from app.models import Photo, Video

    client, data_dir, cid, sf = api

    # A photo, and a clip with its frames.
    buf = io.BytesIO()
    Image.new("RGB", (120, 120), (200, 150, 140)).save(buf, "JPEG")
    photo = client.post(
        "/api/photos", files={"file": ("p.jpg", buf.getvalue(), "image/jpeg")}
    ).json()
    path = make_video()
    try:
        clip = post_video_to(client, path, cid).json()
    finally:
        os.unlink(path)

    frame_ids = [f["id"] for f in clip["frames"]]
    assert (data_dir / clip["path"]).exists()
    for fid in frame_ids:
        assert (data_dir / "photos" / f"{fid}.jpg").exists()

    # Attach the clip's frames to the day, the way a real consult would.
    from app.models import Entry

    s = sf()
    entry = Entry(conversation_id=cid, date=datetime.date(2026, 1, 1), attributes=[])
    s.add(entry)
    s.flush()
    s.add(Photo(entry_id=entry.id, path=f"photos/{photo['id']}.jpg"))
    for fid in frame_ids:
        s.add(Photo(entry_id=entry.id, path=f"photos/{fid}.jpg"))
    s.commit()
    s.close()

    r = client.delete(f"/api/conversations/{cid}")
    assert r.status_code == 200
    assert r.json()["files_removed"] >= 1 + len(frame_ids)

    # Rows gone…
    s = sf()
    assert s.query(Video).filter_by(conversation_id=cid).count() == 0
    s.close()
    # …and the bytes with them.
    assert not (data_dir / clip["path"]).exists(), "clip left on disk"
    assert not (data_dir / "photos" / f"{photo['id']}.jpg").exists(), "photo left on disk"
    for fid in frame_ids:
        assert not (data_dir / "photos" / f"{fid}.jpg").exists(), f"frame {fid} left on disk"
