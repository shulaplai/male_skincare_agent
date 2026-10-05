"""A picked-then-abandoned photo must not live on disk forever (issue #23).

The composer uploads a file the **moment it is picked**, before any Entry can reference
it — so 「撳 ×」, switching body part or closing the page left a jpg with no `Photo` row
and no UI that could ever see or delete it. Measured on a real trial: 15 such files; the
repo's own `data/photos/` already had 6 with a `photos` table of 0 rows, i.e. the leak had
happened quietly and nothing could clean it up.

Two mechanisms pin the fix, and they are checked separately:

* `DELETE /api/photos/{id}` — what removing the chip calls. It must refuse (409) a photo
  an entry owns, because that deletion has to also remove the row the journal renders.
* `sweep_orphan_photos` — the net for a page that closed before it could call anything.
  It must never touch a referenced file, and never touch a file young enough that the
  user could still be about to send it.
"""
import datetime
import os
import time
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import ORPHAN_PHOTO_TTL, app, sweep_orphan_photos
from app.models import ChatMessage, Conversation, Entry, Photo, User, Video


def jpeg(size=(48, 48)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, (200, 150, 140)).save(buf, "JPEG")
    return buf.getvalue()


def upload(client: TestClient, name: str = "p.jpg") -> dict:
    res = client.post("/api/photos", files={"file": (name, jpeg(), "image/jpeg")})
    assert res.status_code == 200, res.text
    return res.json()


def seed_entry(sf) -> tuple[str, str]:
    """A user + conversation + one dated entry; returns (conversation_id, entry_id)."""
    s = sf()
    user = User(name="阿軒")
    s.add(user)
    s.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
    s.add(conv)
    s.flush()
    entry = Entry(conversation_id=conv.id, date=datetime.date(2026, 1, 1), attributes=[])
    s.add(entry)
    s.commit()
    ids = (conv.id, entry.id)
    s.close()
    return ids


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient on a throwaway DB + throwaway data dir, shared with the test."""
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
        yield TestClient(app), tmp_path, sf
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# DELETE /api/photos/{id} — what the × on an attachment calls
# ---------------------------------------------------------------------------


def test_removing_an_unsent_photo_deletes_the_file(api):
    client, data_dir, _ = api
    uploaded = upload(client)
    stored = data_dir / uploaded["path"]
    assert stored.exists()

    res = client.delete(f"/api/photos/{uploaded['id']}")
    assert res.status_code == 200, res.text
    assert not stored.exists(), "移除咗嘅附件唔應該仲留喺 disk"

    # Idempotent enough: the second attempt has nothing to find.
    assert client.delete(f"/api/photos/{uploaded['id']}").status_code == 404


def test_a_photo_an_entry_owns_is_refused_not_deleted(api):
    client, data_dir, sf = api
    uploaded = upload(client)
    _, eid = seed_entry(sf)
    s = sf()
    s.add(Photo(entry_id=eid, path=f"photos/{uploaded['id']}.jpg"))
    s.commit()
    s.close()

    res = client.delete(f"/api/photos/{uploaded['id']}")
    assert res.status_code == 409, res.text
    assert (data_dir / uploaded["path"]).exists(), "記錄擁有嘅相唔可以喺孤兒路徑被刪"
    s = sf()
    assert s.query(Photo).filter_by(entry_id=eid).count() == 1
    s.close()


def test_unknown_or_non_id_photo_is_404(api):
    """The id shape is what keeps arbitrary paths out of the filesystem lookup."""
    client, data_dir, _ = api
    (data_dir / "photos").mkdir(parents=True, exist_ok=True)
    (data_dir / "photos" / "notaphoto.jpg").write_bytes(jpeg())

    assert client.delete("/api/photos/" + "0" * 32).status_code == 404
    assert client.delete("/api/photos/not-a-32-hex-id").status_code == 404
    assert client.delete("/api/photos/..jpg").status_code == 404
    assert (data_dir / "photos" / "notaphoto.jpg").exists(), "唔係 32-hex 嘅 id 唔應該刪到嘢"


# ---------------------------------------------------------------------------
# The sweep — the net for a page that closed before it could call DELETE
# ---------------------------------------------------------------------------


def test_sweep_takes_stale_orphans_and_leaves_everything_else(api):
    _, data_dir, sf = api
    photos = data_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    owned, frame, stale, fresh = "a" * 32, "b" * 32, "c" * 32, "d" * 32
    for pid in (owned, frame, stale, fresh):
        (photos / f"{pid}.jpg").write_bytes(jpeg())

    _, eid = seed_entry(sf)
    s = sf()
    s.add(Photo(entry_id=eid, path=f"photos/{owned}.jpg"))
    conv_id = s.query(Entry).filter_by(id=eid).one().conversation_id
    s.add(Video(conversation_id=conv_id, path="videos/clip.mp4", frames=[frame]))
    s.commit()

    # Only the stale orphan is past the TTL; the fresh one is what a user picked
    # seconds ago and may still be about to send.
    long_ago = time.time() - ORPHAN_PHOTO_TTL - 60
    os.utime(photos / f"{stale}.jpg", (long_ago, long_ago))

    assert sweep_orphan_photos(s) == 1
    assert not (photos / f"{stale}.jpg").exists()
    for pid, why in ((owned, "entry 擁有"), (frame, "未送出嘅片嘅 frame"), (fresh, "啱啱上載")):
        assert (photos / f"{pid}.jpg").exists(), f"{why}嘅檔案被 sweep 錯殺"
    s.close()


def test_uploading_a_photo_runs_the_sweep(api):
    """The wiring, not just the function: picking a photo is the housekeeping moment."""
    client, data_dir, _ = api
    photos = data_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    stale = "e" * 32
    (photos / f"{stale}.jpg").write_bytes(jpeg())
    long_ago = time.time() - ORPHAN_PHOTO_TTL - 60
    os.utime(photos / f"{stale}.jpg", (long_ago, long_ago))

    fresh = upload(client)
    assert not (photos / f"{stale}.jpg").exists()
    assert (data_dir / fresh["path"]).exists(), "啱啱上載嘅相唔可以俾 sweep 刪"


def test_sweep_keeps_a_photo_a_sent_message_still_renders(api):
    """A sent photo can have no Entry at all — the message payload is the only reference.

    `entry_written` is False for e.g. a product question sent with a photo, and
    `format.ts` renders the bubble from `payload.photos` after a reload. Sweeping that
    file would put a 404 in an old reply — a worse bug than the orphan it fixes.
    """
    _, data_dir, sf = api
    photos = data_dir / "photos"
    photos.mkdir(parents=True, exist_ok=True)
    sent = "f" * 32
    (photos / f"{sent}.jpg").write_bytes(jpeg())
    conv_id, _ = seed_entry(sf)
    s = sf()
    s.add(
        ChatMessage(
            conversation_id=conv_id,
            role="user",
            text="睇下呢張",
            payload={"photos": [sent], "clip": None},
        )
    )
    s.commit()
    long_ago = time.time() - ORPHAN_PHOTO_TTL - 60
    os.utime(photos / f"{sent}.jpg", (long_ago, long_ago))

    assert sweep_orphan_photos(s) == 0
    assert (photos / f"{sent}.jpg").exists(), "送出咗嘅相唔可以俾 sweep 刪，唔係舊訊息會變 404"
    s.close()


# ---------------------------------------------------------------------------
# DELETE /api/entries/{eid}/photos/{pid} — the record path, previously untested
# ---------------------------------------------------------------------------


def test_delete_entry_photo_route_removes_the_row_and_the_file(api):
    client, data_dir, sf = api
    uploaded = upload(client)
    _, eid = seed_entry(sf)
    s = sf()
    s.add(Photo(entry_id=eid, path=f"photos/{uploaded['id']}.jpg"))
    s.commit()
    s.close()

    res = client.delete(f"/api/entries/{eid}/photos/{uploaded['id']}")
    assert res.status_code == 200, res.text
    assert not (data_dir / uploaded["path"]).exists()
    s = sf()
    assert s.query(Photo).filter_by(entry_id=eid).count() == 0
    s.close()

    # An entry that does not own that photo (or none at all) must not delete it.
    assert client.delete(f"/api/entries/{eid}/photos/{'f' * 32}").status_code == 404
