"""A clip is a clip: the user uploaded a *video*, and the frame sampling is backstage.

The user's instruction (2026-10-01) was explicit: don't make them watch a row of
extracted frames, and don't tell them about the sampling/compression. So:

* `analyze` gets a note saying it is a clip (and, when the clip yielded fewer than two
  usable frames, a one-line Cantonese hint about moving the camera — no numbers);
* `advise` is told to say 「條片」 and never 「幾張相」／格數／抽格;
* the persisted user message carries `clip`, so a reload renders the video chip instead
  of a photo.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import prompts
from app.agent.graph import build_graph
from app.agent.schemas import Advice, SkinAnalysis
from app.db import Base
from app.models import ChatMessage, Conversation, User
from app.rag import DeterministicEmbedder


def _state(**kw) -> dict:
    base = {
        "user_text": "今日影咗條片",
        "analysis": {"observes_skin": True, "summary": "T 字位偏油", "metrics": [], "attributes": []},
        "tool_results": {},
        "tool_calls": [],
        "first_checkin": False,
        "vision_reason": "used",
        "vision_used": True,
    }
    base.update(kw)
    return base


# ---- analyze prompt ---------------------------------------------------------

def test_clip_note_talks_about_a_video():
    p = prompts.build_analyze_prompt("今日影咗條片", True, photo_viewed=True, clip={"duration": 12.4, "frames": 6})
    assert "一段短片" in p
    assert "唔好" in p and "幾張相" in p, "要明文禁止數字數"


def test_photo_note_is_unchanged_without_a_clip():
    p = prompts.build_analyze_prompt("今日影咗張相", True, photo_viewed=True)
    assert "皮膚相" in p
    assert "一段短片" not in p


def test_low_frame_clip_gets_a_camera_hint_not_frame_talk():
    p = prompts.build_analyze_prompt("影咗條片", True, photo_viewed=True, clip={"duration": 20.0, "frames": 1})
    assert "鏡頭慢慢掃過" in p
    assert "唔好" in p and "格數" in p


# ---- advise prompt ----------------------------------------------------------

def test_advise_prompt_forbids_frame_language():
    p = prompts.build_advise_prompt(_state(clip={"duration": 12.4, "frames": 6}))
    assert "一段短片" in p
    assert "唔好" in p
    for banned in ("幾張相", "格數", "抽格"):
        assert banned in p, f"要有明文禁止：{banned}"


def test_advise_prompt_has_no_clip_block_for_photos():
    p = prompts.build_advise_prompt(_state())
    assert "一段短片" not in p


# ---- persistence ------------------------------------------------------------

class StubLLM:
    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=True, summary="T 字位偏油",
                attributes=[{"key": "oiliness", "severity": 2, "note": ""}],
            )
        return Advice(reply="睇到你條片，T 字位偏油。", items=["做好控油"], disclaimer="僅供參考", escalate=False)

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def _run(tmp_path, clip):
    engine = create_engine(f"sqlite:///{tmp_path / 'clip.db'}")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
    s.add(c)
    s.commit()
    cid = c.id
    s.close()

    g = build_graph(llm=StubLLM(), vision_llm=StubLLM(), session_factory=sf, embedder=DeterministicEmbedder())
    g.invoke(
        {
            "conversation_id": cid,
            "user_text": "影咗條片",
            "photo_paths": [],
            "clip": clip,
            "cloud_analysis": True,
            "trace": [],
        }
    )
    return sf, cid


def test_user_message_payload_carries_the_clip(tmp_path):
    sf, cid = _run(tmp_path, {"duration": 12.4, "frames": 6})
    s = sf()
    try:
        user_msg = (
            s.query(ChatMessage)
            .filter_by(conversation_id=cid, role="user")
            .order_by(ChatMessage.id.desc())
            .first()
        )
        assert user_msg.payload["clip"] == {"duration": 12.4, "frames": 6}
    finally:
        s.close()


def test_photo_message_has_no_clip_flag(tmp_path):
    sf, cid = _run(tmp_path, None)
    s = sf()
    try:
        user_msg = (
            s.query(ChatMessage)
            .filter_by(conversation_id=cid, role="user")
            .order_by(ChatMessage.id.desc())
            .first()
        )
        assert not user_msg.payload.get("clip")
    finally:
        s.close()
