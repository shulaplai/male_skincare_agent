"""Uploads must fail *readably* — measured, not imagined.

Both of these were found by driving the real UI as a user, and both were user-visible:

* a HEIC file (the **default** iPhone camera format) returned HTTP 500 and the composer
  showed 「✗ 上傳失敗：HTTP 500」 — nothing to act on, and the commonest iPhone path;
* a 15-byte text file named `.mp4` came back with the whole ffmpeg banner (~1.6 KB of
  `ffmpeg version 7.1 … --enable-libx265 …` plus the server-side temp path) rendered
  verbatim in the same chip.

The rule these pin: whatever the user did, the message has to be short, Cantonese and
actionable; the diagnostic detail goes to the log.
"""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import Conversation, User
from app.photo import UnreadableImage, compress_image
from app.video import VideoDecodeError, extract_frames


# ---------------------------------------------------------------------------
# Photos: not-an-image → 415 with a message a person can use
# ---------------------------------------------------------------------------


def test_compress_image_rejects_non_image_bytes():
    with pytest.raises(UnreadableImage):
        compress_image(b"this is not an image at all")


def test_compress_image_rejects_truncated_jpeg():
    buf = BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, "JPEG")
    truncated = buf.getvalue()[: len(buf.getvalue()) // 3]
    with pytest.raises(UnreadableImage):
        compress_image(truncated)


def test_photo_upload_is_415_not_500(tmp_path, monkeypatch):
    """A HEIC-ish payload (Pillow cannot open it without `pillow-heif`)."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    client = TestClient(app)
    res = client.post(
        "/api/photos",
        files={"file": ("IMG_1234.heic", b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00", "image/heic")},
    )
    assert res.status_code == 415, res.text
    detail = res.json()["detail"]
    assert "HEIC" in detail, detail
    assert "最相容" in detail, "the message must tell the user what to do"
    # Nothing half-written is left behind for a rejected upload.
    #
    # ⚠️ 呢句本來係 `assert not list(...) if exists() else True` —— 條件表達式嘅
    # 優先次序令目錄唔存在時成句等於 `assert True`，即係**永遠唔會紅**。而「目錄
    # 唔存在」正好就係「乜都冇寫低」嘅情況，所以佢喺最需要檢查嘅時候靜靜通過。
    # 寫法：先斷言目錄狀態，再斷言內容。
    photos = tmp_path / "photos"
    leftovers = list(photos.glob("*.jpg")) if photos.exists() else []
    assert leftovers == [], f"rejected upload left files behind: {leftovers}"
    assert not photos.exists() or not any(photos.iterdir()), (
        "被拒嘅上載唔應該喺 disk 留低任何嘢（包括非 .jpg）"
    )


# ---------------------------------------------------------------------------
# EXIF orientation: the stored photo (and what vision sees) must be upright
# ---------------------------------------------------------------------------


def test_exif_orientation_is_applied():
    """Raw pixels sideways + orientation=6 → stored image is the upright one.

    Before this the file was saved unrotated with the tag dropped (measured: 2048×1536
    in → 1024×768 out, subject ~90° off, confirmed by reading the stored file back), so
    the user's own preview and the vision model both saw a sideways face.
    """
    upright = Image.new("RGB", (40, 20), "white")
    sideways = upright.transpose(Image.ROTATE_90)  # (20, 40): needs a 90° CW turn back
    exif = sideways.getexif()
    exif[274] = 6  # EXIF Orientation: rotate 90° CW to display
    buf = BytesIO()
    sideways.save(buf, "JPEG", exif=exif)

    stored = Image.open(BytesIO(compress_image(buf.getvalue())))
    assert stored.size == (40, 20)


def test_exif_orientation_absent_keeps_the_pixels():
    upright = Image.new("RGB", (40, 20), "white")
    buf = BytesIO()
    upright.save(buf, "JPEG")
    assert Image.open(BytesIO(compress_image(buf.getvalue()))).size == (40, 20)


# ---------------------------------------------------------------------------
# Videos: unreadable container → short message, banner to the log
# ---------------------------------------------------------------------------


def test_unreadable_clip_message_is_short(tmp_path):
    fake = tmp_path / "notvideo.mp4"
    fake.write_text("not a video")
    with pytest.raises(VideoDecodeError) as ei:
        extract_frames(fake)
    msg = str(ei.value)
    assert "讀唔到" in msg
    assert "ffmpeg version" not in msg, "the ffmpeg banner must not reach the user"
    assert len(msg) < 160, msg


def test_video_upload_detail_has_no_ffmpeg_banner(tmp_path, monkeypatch):
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
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    try:
        session = sf()
        user = User(name="阿軒")
        session.add(user)
        session.flush()
        conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
        session.add(conv)
        session.commit()
        cid = conv.id
        session.close()

        client = TestClient(app)
        res = client.post(
            f"/api/videos?cid={cid}",
            files={"file": ("clip.mp4", b"not a video", "video/mp4")},
        )
        assert res.status_code == 422, res.text
        detail = res.json()["detail"]
        assert "ffmpeg version" not in detail
        assert len(detail) < 200, detail
    finally:
        app.dependency_overrides.clear()
