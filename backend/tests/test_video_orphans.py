"""A picked-then-abandoned clip must not live on disk forever (issue #27).

`POST /api/videos` writes three things the moment a file is picked: the clip itself
(`data/videos/<id>.mp4`), a `Video` row, and its sampled frames as ordinary photos. The
composer's 「移除皮膚影片」 button only cleared local state, so all three stayed until the
whole conversation was deleted — the sibling of the picked-photo leak fixed in #23, and
one `sweep_orphan_photos` deliberately does **not** cover (`Video.frames` is on that
sweep's protected list so a clip waiting to be sent keeps its frames).

`DELETE /api/videos/{id}` closes it, and the tests pin the two rules that mirror the
photo route: an unattached clip goes away completely, and a clip whose frames an entry
already references answers 409 instead of losing files the journal still renders.
"""
import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import Conversation, Entry, Photo, User, Video


def seed_conversation(sf) -> tuple[str, str]:
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


def seed_clip(sf, data_dir, *, frames: int = 2, suffix: str = ".mp4") -> tuple[str, list[str]]:
    """A stored clip + its frame files + the `Video` row, as the upload route leaves them."""
    conv_id, _ = seed_conversation(sf)
    video_id = "a1b2c3d4" * 4
    frame_ids = [f"{i:032x}" for i in range(1, frames + 1)]
    (data_dir / "videos").mkdir(parents=True, exist_ok=True)
    (data_dir / "photos").mkdir(parents=True, exist_ok=True)
    (data_dir / "videos" / f"{video_id}{suffix}").write_bytes(b"not really a clip")
    for fid in frame_ids:
        (data_dir / "photos" / f"{fid}.jpg").write_bytes(b"frame")
    s = sf()
    s.add(
        Video(
            id=video_id,
            conversation_id=conv_id,
            path=f"videos/{video_id}{suffix}",
            duration=12.0,
            frames=frame_ids,
        )
    )
    s.commit()
    s.close()
    return video_id, frame_ids


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


def test_removing_an_unsent_clip_deletes_the_clip_and_every_frame(api):
    client, data_dir, sf = api
    video_id, frame_ids = seed_clip(sf, data_dir)
    clip_file = data_dir / "videos" / f"{video_id}.mp4"
    assert clip_file.exists()

    res = client.delete(f"/api/videos/{video_id}")
    assert res.status_code == 200, res.text
    assert res.json()["frames_removed"] == len(frame_ids)

    assert not clip_file.exists(), "移除咗嘅片唔應該仲留喺 disk"
    for fid in frame_ids:
        assert not (data_dir / "photos" / f"{fid}.jpg").exists(), "未送出嘅片嘅 frame 要一齊清"
    s = sf()
    assert s.query(Video).filter_by(id=video_id).first() is None
    s.close()

    # The second attempt has nothing to find.
    assert client.delete(f"/api/videos/{video_id}").status_code == 404


def test_a_clip_whose_frames_an_entry_owns_is_refused_not_deleted(api):
    """The 409 mirrors the photo route: deleting rows the journal renders is not this path's job."""
    client, data_dir, sf = api
    video_id, frame_ids = seed_clip(sf, data_dir)
    _, eid = seed_conversation(sf)
    s = sf()
    s.add(Photo(entry_id=eid, path=f"photos/{frame_ids[0]}.jpg"))
    s.commit()
    s.close()

    res = client.delete(f"/api/videos/{video_id}")
    assert res.status_code == 409, res.text
    assert (data_dir / "videos" / f"{video_id}.mp4").exists()
    for fid in frame_ids:
        assert (data_dir / "photos" / f"{fid}.jpg").exists(), "記錄擁有嘅 frame 唔可以喺孤兒路徑被刪"
    s = sf()
    assert s.query(Video).filter_by(id=video_id).first() is not None
    s.close()


def test_unknown_clip_is_404_and_touches_nothing(api):
    client, data_dir, _ = api
    (data_dir / "videos").mkdir(parents=True, exist_ok=True)
    (data_dir / "videos" / "bystander.mp4").write_bytes(b"x")

    assert client.delete("/api/videos/" + "0" * 32).status_code == 404
    assert client.delete("/api/videos/not-a-32-hex-id").status_code == 404
    assert (data_dir / "videos" / "bystander.mp4").exists()


def test_a_re_encoded_clip_is_deleted_too(api):
    """`compress_video` renames the file to `<id>.c.mp4`; looking only at the plain name
    was a real bug once — the clip could not be found, so it could not be deleted."""
    client, data_dir, sf = api
    video_id, frame_ids = seed_clip(sf, data_dir, frames=1, suffix=".c.mp4")
    compressed = data_dir / "videos" / f"{video_id}.c.mp4"
    assert compressed.exists()

    assert client.delete(f"/api/videos/{video_id}").status_code == 200
    assert not compressed.exists()
    assert not (data_dir / "photos" / f"{frame_ids[0]}.jpg").exists()
