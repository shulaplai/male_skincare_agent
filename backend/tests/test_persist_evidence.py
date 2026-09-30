"""`Entry` is only written when the turn actually carries skin evidence.

The whole T1–T5 family in `docs/backend-flow.md` §6 came from one thing: every chat
message was treated as a check-in. `ANALYZE_SYSTEM` says "未提及就畀 0", so asking
about a product produced an all-zero analysis that *replaced* the day's real readings.
Because only one agent timeline event per day is allowed, the resulting fake "改善"
was then frozen — a later real check-in could restore the attributes but never the
event. Measured on the live path: the model returns all six attributes as 0 for
「呢支精華得唔得？」and says so in its own reply.

The gate is `SkinAnalysis.observes_skin` (LLM-judged) OR `vision_used`.

The stub is told what the model "decided" rather than guessing from the text: the
judgement belongs to the model, and a test that re-implemented it with keywords would
be testing the keyword list instead.
"""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.schemas import Advice, SkinAnalysis
from app.db import Base
from app.models import ChatMessage, Conversation, Entry, Insight, Photo, TimelineEvent, User
from app.rag import DeterministicEmbedder

# Severity the stub reports when it *did* observe skin.
SEV = 3


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed_conversation(sf) -> str:
    s = sf()
    u = User(name="阿軒")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    s.add(c)
    s.commit()
    cid = c.id
    s.close()
    return cid


class StubLLM:
    """Returns the judgement the test asks for.

    `observes` and `severity` are independent knobs on purpose: the gate and the
    values are separate concerns, and a test of the gate should not be entangled with
    what the model rated. (The *real* model happens to return all zeros when it
    observed nothing — `ANALYZE_SYSTEM` says「未提及就畀 0」— which is precisely why the
    old code corrupted the day. That behaviour is documented, not simulated here.)
    """

    def __init__(self, observes: bool, severity: int = SEV):
        self.observes = observes
        self.severity = severity

    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return SkinAnalysis(
                observes_skin=self.observes,
                summary="有觀察" if self.observes else "（未提及皮膚狀況）",
                attributes=[
                    {"key": "acne", "severity": self.severity, "note": ""},
                    {"key": "oiliness", "severity": self.severity, "note": ""},
                ],
            )
        return Advice(reply="建議如下。", items=["做好保濕"], disclaimer="已加免責", escalate=False)

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def run(sf, llm, cid, text, *, photo_paths=None, cloud=False, vision_llm=None):
    g = build_graph(
        llm=llm, vision_llm=vision_llm or llm, session_factory=sf, embedder=DeterministicEmbedder()
    )
    return g.invoke(
        {
            "conversation_id": cid,
            "user_text": text,
            "photo_paths": photo_paths or [],
            "cloud_analysis": cloud,
            "trace": [],
        }
    )


def counts(sf, cid) -> dict:
    s = sf()
    try:
        return {
            "entries": s.query(Entry).filter_by(conversation_id=cid).count(),
            "timeline": s.query(TimelineEvent).filter_by(conversation_id=cid).count(),
            "insights": s.query(Insight).filter_by(conversation_id=cid).count(),
            "messages": s.query(ChatMessage).filter_by(conversation_id=cid).count(),
            "photos": s.query(Photo).count(),
        }
    finally:
        s.close()


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


def test_a_question_writes_no_entry_no_timeline_and_no_memory():
    """T1/T2/T4: a product question must not become a day of skin data."""
    sf = make_factory()
    cid = seed_conversation(sf)

    res = run(sf, StubLLM(observes=False), cid, "呢支精華有 2% 水楊酸同菸鹼胺，值唔值得買？")

    c = counts(sf, cid)
    assert c["entries"] == 0, "a question must not create an Entry"
    assert c["timeline"] == 0
    assert c["insights"] == 0, "a question must not create memory"
    # The conversation itself is still persisted (display truth).
    assert c["messages"] == 2

    detail = [t for t in res["trace"] if t["node"] == "persist"][0]["detail"]
    assert detail["observes_skin"] is False
    assert detail["entry_written"] is False


def test_a_skin_description_does_write_the_entry():
    sf = make_factory()
    cid = seed_conversation(sf)

    run(sf, StubLLM(observes=True), cid, "今晚塊面爆緊瘡，T 字位好油")

    s = sf()
    e = s.query(Entry).filter_by(conversation_id=cid).first()
    assert e is not None
    assert {a["key"]: a["severity"] for a in e.attributes} == {"acne": SEV, "oiliness": SEV}
    assert e.note == "今晚塊面爆緊瘡，T 字位好油"
    s.close()


def test_vision_used_forces_the_entry_even_if_the_model_says_false(monkeypatch):
    """A photo the vision model actually read IS evidence, whatever the flag says.

    Patching `load_photo_b64` / `photo_exists` avoids needing a real image on disk —
    the thing under test is the `observes_skin or vision_used` gate, not image I/O.
    """
    sf = make_factory()
    cid = seed_conversation(sf)
    monkeypatch.setattr(
        "app.agent.graph.load_photo_b64", lambda pid: {"media_type": "image/jpeg", "data": "x"}
    )
    monkeypatch.setattr("app.agent.graph.photo_exists", lambda pid: True)

    res = run(
        sf,
        StubLLM(observes=False, severity=SEV),  # the model wrongly claims it observed nothing
        cid,
        "（已上傳皮膚相）",
        photo_paths=["a" * 32],
        cloud=True,
    )

    assert res["vision_used"] is True, "sanity: the vision branch really ran"

    s = sf()
    e = s.query(Entry).filter_by(conversation_id=cid).first()
    assert e is not None, "a photo the vision model read is evidence by definition"
    assert {a["key"]: a["severity"] for a in e.attributes} == {"acne": SEV, "oiliness": SEV}
    assert s.query(Photo).count() == 1, "the photo still attaches to the day"
    s.close()


def test_today_entry_is_untouched_by_a_later_question():
    """T1/T2/T3: the day's record survives a question, and the timeline stays honest."""
    sf = make_factory()
    cid = seed_conversation(sf)
    today = datetime.date.today()

    # A worse reading yesterday, so today's check-in can produce a real change line.
    s = sf()
    s.add(
        Entry(
            conversation_id=cid,
            date=today - datetime.timedelta(days=1),
            note="昨日",
            attributes=[
                {"key": "acne", "severity": 3, "note": ""},
                {"key": "oiliness", "severity": 3, "note": ""},
            ],
        )
    )
    s.commit()
    s.close()

    run(sf, StubLLM(observes=True, severity=2), cid, "今晚塊面爆緊瘡，T 字位好油")

    s = sf()
    today_entry = s.query(Entry).filter_by(conversation_id=cid, date=today).first()
    assert today_entry is not None
    before_attrs = list(today_entry.attributes)
    before_note = today_entry.note
    before_tl = [t.text for t in s.query(TimelineEvent).filter_by(conversation_id=cid).all()]
    before_ins = s.query(Insight).filter_by(conversation_id=cid).count()
    s.close()

    # Now ask about a product.
    run(sf, StubLLM(observes=False), cid, "呢支精華有 2% 水楊酸，得唔得？")

    s = sf()
    today_entry = s.query(Entry).filter_by(conversation_id=cid, date=today).first()
    assert list(today_entry.attributes) == before_attrs, "T1: the day's attributes must not be rewritten"
    assert today_entry.note == before_note, "T3: the day's note must not be overwritten"
    assert [t.text for t in s.query(TimelineEvent).filter_by(conversation_id=cid).all()] == before_tl, (
        "T2: the timeline must not gain a fake event"
    )
    assert s.query(Insight).filter_by(conversation_id=cid).count() == before_ins, (
        "T4: no fake「正常」memory from a question"
    )
    # …and the conversation still gained the two turns.
    assert s.query(ChatMessage).filter_by(conversation_id=cid).count() == 4
    s.close()


def test_a_question_does_not_consume_first_checkin():
    """T5: the onboarding branch is for the first real check-in, not for a question."""
    sf = make_factory()
    cid = seed_conversation(sf)

    first = run(sf, StubLLM(observes=False), cid, "呢支精華得唔得？")
    assert [t for t in first["trace"] if t["node"] == "tools"][0]["detail"]["first_checkin"] is True

    second = run(sf, StubLLM(observes=True), cid, "今晚塊面爆緊瘡")
    assert [t for t in second["trace"] if t["node"] == "tools"][0]["detail"]["first_checkin"] is True, (
        "the real first check-in must still get the onboarding branch"
    )


# ---------------------------------------------------------------------------
# The advice prompt must not leak the internal flag or abandon the question
# ---------------------------------------------------------------------------


def test_advise_prompt_strips_the_internal_flag():
    """Found by running a real LLM: it narrated「分析顯示 observes_skin=false」to the user."""
    from app.agent.prompts import build_advise_prompt

    prompt = build_advise_prompt(
        {
            "user_text": "呢支精華得唔得？",
            "analysis": {"observes_skin": False, "summary": "x", "attributes": []},
            "tool_results": [],
            "first_checkin": True,
            "recent_messages": [],
        }
    )
    assert "observes_skin" not in prompt, "內部欄位名唔可以出現喺 prompt 度（model 會照講返）"
    assert "今次唔係皮膚紀錄" in prompt
    assert "正面回答佢今次問嘅嘢" in prompt


def test_a_question_does_not_trigger_the_onboarding_block():
    """`first_checkin` is "no Entry ever", which a question-only first turn also satisfies."""
    from app.agent.prompts import build_advise_prompt

    base = {
        "user_text": "呢支精華得唔得？",
        "tool_results": [],
        "first_checkin": True,  # no Entry yet — true even though nothing was observed
        "recent_messages": [],
    }
    asked = build_advise_prompt({**base, "analysis": {"observes_skin": False}})
    observed = build_advise_prompt({**base, "analysis": {"observes_skin": True}})

    assert "第一個紀錄" not in asked, "問問題唔應該觸發 onboarding 引導"
    assert "第一個紀錄" in observed, "真嘅首次打卡仍然要有 onboarding 引導"


def test_vision_used_also_counts_as_observed_for_the_advise_prompt():
    from app.agent.prompts import build_advise_prompt

    prompt = build_advise_prompt(
        {
            "user_text": "（已上傳皮膚相）",
            "analysis": {"observes_skin": False},  # model wrongly says no
            "tool_results": [],
            "first_checkin": True,
            "recent_messages": [],
            "vision_used": True,
        }
    )
    assert "第一個紀錄" in prompt
    assert "今次唔係皮膚紀錄" not in prompt
