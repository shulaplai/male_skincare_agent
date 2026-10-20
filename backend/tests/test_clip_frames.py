"""A clip must actually reach vision — otherwise the model invents a reading.

The incident this locks down (2026-10-20): the browser sent
`video: {duration, frames}` with an empty `photo_paths`. `analyze` therefore saw
`has_photo=False` and ran the *text-only* path with the placeholder text
「（已上傳皮膚影片）」 as the only evidence. The model answered as if it had watched
the clip («睇你條片… 泛紅由 0 回升到 1 分»), marked `observes_skin=True`, and
`persist` wrote a six-attribute day that nobody ever looked at.

Three separate guarantees are tested here:

1. `resolve_clip_frames` turns `video_id` into `photo_paths` server-side, so a
   client cannot forget and `retry` (which replays the stored payload) works.
2. A clip whose frames are gone stays a clip (`clip` kept → the UI renders one
   video chip, not a row of photos) but is marked `unavailable`.
3. Every prompt branch that has a clip **without** vision says so, and forbids
   「睇你條片」/concrete numbers — in both `analyze` and `advise`.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import prompts, service
from app.config import settings
from app.db import Base
from app.models import Conversation, User, Video


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Temp data dir + in-memory DB, wired into `service` (which imports the names)."""
    from pathlib import Path

    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    monkeypatch.setattr(service, "SessionLocal", sf)

    session = sf()
    user = User(name="阿軒")
    session.add(user)
    session.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚")
    session.add(conv)
    session.commit()

    def add_clip(frames: int = 3, make_files: int | None = None) -> tuple[str, list[str]]:
        """A `Video` row with `frames` ids, and real files for the first `make_files`."""
        ids = [f"{i:032x}" for i in range(1, frames + 1)]
        photos = Path(settings.data_dir) / "photos"
        photos.mkdir(parents=True, exist_ok=True)
        for pid in ids[: frames if make_files is None else make_files]:
            # `photo_exists` only checks the id shape and that the file is there, so
            # the bytes do not need to be decodable by PIL here.
            (photos / f"{pid}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        video = Video(
            id=f"v{len(ids):02d}" + "0" * 29,
            conversation_id=conv.id,
            path="videos/x.mp4",
            duration=12.4,
            frames=ids,
        )
        session.add(video)
        session.commit()
        return video.id, ids

    yield {"conv": conv.id, "add_clip": add_clip, "session": session}
    session.close()


# ---- resolution -------------------------------------------------------------

def test_frames_become_photo_paths(db):
    """The whole point: no photo_paths from the client still means vision sees frames."""
    video_id, ids = db["add_clip"](frames=3)

    paths, clip = service.resolve_clip_frames([], {"duration": 12.4, "frames": 6, "video_id": video_id})

    assert paths == ids
    # The count is re-derived from the row, not trusted from the client.
    assert clip["frames"] == 3
    assert "unavailable" not in clip


def test_client_photo_paths_win(db):
    """A clip plus explicitly attached photos keeps the photos (no double-vision)."""
    video_id, _ = db["add_clip"](frames=3)

    paths, clip = service.resolve_clip_frames(
        ["a" * 32], {"duration": 12.4, "frames": 6, "video_id": video_id}
    )

    assert paths == ["a" * 32]
    assert clip["video_id"] == video_id


def test_unknown_video_keeps_clip_but_flags_unavailable(db):
    """Frames gone ≠ "no clip": the chip must stay, the vision claim must go."""
    paths, clip = service.resolve_clip_frames([], {"duration": 9.0, "frames": 4, "video_id": "f" * 32})

    assert paths == []
    assert clip["unavailable"] is True
    assert clip["frames"] == 0


def test_missing_frame_files_are_skipped(db):
    """`Video.frames` can outlive the JPEGs (sweep, manual delete) — never hand over duds."""
    video_id, ids = db["add_clip"](frames=3, make_files=1)

    paths, clip = service.resolve_clip_frames([], {"frames": 3, "video_id": video_id})

    assert paths == ids[:1]
    assert clip["frames"] == 1


def test_no_clip_is_a_no_op(db):
    assert service.resolve_clip_frames(None, None) == ([], None)
    assert service.resolve_clip_frames(["a" * 32], None) == (["a" * 32], None)


def test_run_consult_hands_frames_to_the_graph(db, monkeypatch):
    """End of the chain: the graph really receives the ids (not just a helper result)."""
    video_id, ids = db["add_clip"](frames=3)
    captured: dict = {}

    class Graph:
        def invoke(self, state):
            captured.update(state)
            return {"vision_used": True, "trace": []}

    monkeypatch.setattr(service, "_build_consult_graph", lambda: (Graph(), {}))
    monkeypatch.setattr(service, "open_consult", lambda cid, paths: True)
    monkeypatch.setattr(service, "write_run_log", lambda *a, **k: None)

    service.run_consult(
        db["conv"],
        "（已上傳皮膚影片）",
        None,
        {"duration": 12.4, "frames": 6, "video_id": video_id},
    )

    assert captured["photo_paths"] == ids
    assert captured["clip"]["frames"] == 3


# ---- prompt honesty ---------------------------------------------------------

def test_analyze_prompt_with_unseen_clip_forbids_pretending():
    p = prompts.build_analyze_prompt("（已上傳皮膚影片）", False, clip={"frames": 0, "unavailable": True})

    assert "睇唔到" in p
    # The placeholder text must not be presented as something that was looked at.
    assert "（無相，純文字）" not in p


def test_analyze_prompt_still_says_no_photo_without_clip():
    p = prompts.build_analyze_prompt("下巴有啲紅", False)
    assert "（無相，純文字）" in p


def _advise_state(**kw) -> dict:
    base = {
        "user_text": "（已上傳皮膚影片）",
        "analysis": {"observes_skin": True, "summary": "偏油", "attributes": []},
        "tool_results": {},
        "tool_calls": [],
        "first_checkin": False,
        "observed": True,
        "vision_reason": "used",
        "vision_used": True,
        "clip": {"duration": 12.4, "frames": 6},
    }
    base.update(kw)
    return base


def test_advise_prompt_says_it_could_not_see_an_unwatched_clip():
    p = prompts.build_advise_prompt(_advise_state(vision_used=False))

    assert "睇唔到" in p
    assert "幾張相" in p  # the leak guard is still there


def test_advise_prompt_keeps_the_video_wording_when_it_did_watch():
    p = prompts.build_advise_prompt(_advise_state())

    assert "條片" in p
    assert "睇唔到" not in p
