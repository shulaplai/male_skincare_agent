"""Same-day Entry merge — issue #21 policy B.

One `Entry` per day (doctrine #5). A second check-in used to replace the day's
readings wholesale, so a message that mentioned one attribute reset the other five
to 0 — and the anchors, the derived memories and the product verdict all read those
values. Measured on the live path: 「今朝爆多咗兩粒」 turned acne 2→1 and flipped a
product from `good` to `caution`, because `recommend.TRIGGER_FLOOR` is 2.

Policy B (chosen by the user): a later check-in only replaces the readings it
actually mentioned. `Attribute.mentioned` is the signal — the model knows which
attributes this turn is about; a severity of 0 alone cannot say whether it means
"looked, it is clear" or "the user did not talk about this".

`mentioned` defaults to True, so an output that omits it (older payloads, FakeLLM)
keeps the old replace-the-day behaviour. That is deliberate: a wrong default in the
other direction would freeze the day silently.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.attributes import merge_attributes, merge_metrics, merge_note, severity_map
from app.agent.graph import build_graph
from app.agent.prompts import build_advise_prompt
from app.agent.schemas import Advice, SkinAnalysis
from app.db import Base
from app.models import ChatMessage, Conversation, Entry, Insight, TimelineEvent, User
from app.rag import DeterministicEmbedder

# ---------------------------------------------------------------------------
# Pure merge helpers
# ---------------------------------------------------------------------------


def test_a_mentioned_attribute_replaces_and_an_unmentioned_one_survives():
    existing = [
        {"key": "acne", "severity": 2, "note": "兩粒", "mentioned": True},
        {"key": "oiliness", "severity": 1, "note": "", "mentioned": True},
    ]
    incoming = [
        {"key": "acne", "severity": 1, "note": "", "mentioned": True},
        {"key": "oiliness", "severity": 0, "note": "", "mentioned": False},
        {"key": "dryness", "severity": 0, "note": "", "mentioned": False},
    ]

    merged, kept = merge_attributes(existing, incoming)

    assert severity_map(merged) == {"acne": 1, "oiliness": 1, "dryness": 0}, (
        "未提及嘅唔可以變 0；但當日完全冇讀數嘅 attribute 唯有照收（entry 係新嘅）"
    )
    assert kept == ["oiliness"], "trace 要睇得到邊幾個係沿用舊讀數"
    assert [a["key"] for a in merged] == ["acne", "oiliness", "dryness"], "固定 ATTRIBUTE_KEYS 次序"


def test_an_attribute_the_turn_really_mentions_does_replace():
    merged, kept = merge_attributes(
        [{"key": "acne", "severity": 2, "note": "", "mentioned": True}],
        [{"key": "acne", "severity": 0, "note": "", "mentioned": True}],
    )
    assert severity_map(merged) == {"acne": 0}, "真係講咗好返，就要寫入 0"
    assert kept == []


def test_a_first_check_in_with_no_prior_reading_takes_what_it_has():
    merged, kept = merge_attributes([], [{"key": "acne", "severity": 2, "note": "", "mentioned": False}])
    assert severity_map(merged) == {"acne": 2}, "冇舊讀數就冇嘢可以保留"
    assert kept == []


def test_metrics_merge_by_key_and_keep_untouched_rows():
    merged = merge_metrics(
        [{"key": "油光", "value": "中等", "dir": "bad"}],
        [{"key": "新暗瘡", "value": "兩粒", "dir": "bad"}],
    )
    assert [m["key"] for m in merged] == ["油光", "新暗瘡"], "朝早嗰行唔可以被抹走"

    merged = merge_metrics([{"key": "油光", "value": "中等", "dir": "bad"}], [{"key": "油光", "value": "輕微", "dir": "good"}])
    assert merged == [{"key": "油光", "value": "輕微", "dir": "good"}], "同一個 key 就係更新"


def test_the_note_keeps_the_whole_day_without_doubling():
    assert merge_note("", "下巴爆咗兩粒") == "下巴爆咗兩粒"
    assert merge_note("下巴爆咗兩粒", "下巴爆咗兩粒") == "下巴爆咗兩粒", "同一句唔會寫兩次"
    assert merge_note("下巴爆咗兩粒", "") == "下巴爆咗兩粒"
    assert merge_note("下巴爆咗兩粒", "食咗辣") == "下巴爆咗兩粒\n食咗辣"


# ---------------------------------------------------------------------------
# Through the real graph, on one day
# ---------------------------------------------------------------------------


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


def attr(key, severity, mentioned):
    return {"key": key, "severity": severity, "note": "", "mentioned": mentioned}


class ScriptedLLM:
    """Returns the analyses the test wrote, in order (one per check-in)."""

    def __init__(self, analyses: list[SkinAnalysis]):
        self._analyses = list(analyses)

    def structured(self, system, user, schema):
        if schema is SkinAnalysis:
            return self._analyses.pop(0)
        return Advice(reply="建議如下。", items=["做好保濕"], disclaimer="已加免責", escalate=False)

    def structured_vision(self, system, user, schema, images):
        return self.structured(system, user, schema)


def run(sf, llm, cid, text):
    g = build_graph(llm=llm, vision_llm=llm, session_factory=sf, embedder=DeterministicEmbedder())
    return g.invoke(
        {
            "conversation_id": cid,
            "user_text": text,
            "photo_paths": [],
            "cloud_analysis": False,
            "trace": [],
        }
    )


def test_a_vague_later_message_no_longer_erases_the_day():
    """The exact chain from issue #21: memories were strengthened with a 0 nobody said."""
    sf = make_factory()
    cid = seed_conversation(sf)
    llm = ScriptedLLM(
        [
            SkinAnalysis(
                observes_skin=True,
                summary="下巴有兩粒，T 字位油",
                attributes=[attr("acne", 2, True), attr("oiliness", 1, True)],
            ),
            SkinAnalysis(
                observes_skin=True,
                summary="爆多咗",
                attributes=[attr("acne", 3, True), attr("oiliness", 0, False)],
            ),
        ]
    )

    run(sf, llm, cid, "今日下巴爆咗兩粒瘡，T字位好油")
    second = run(sf, llm, cid, "尋晚打邊爐食咗辣底，今朝爆多咗兩粒")

    s = sf()
    entry = s.query(Entry).filter_by(conversation_id=cid).one()
    assert severity_map(entry.attributes) == {"acne": 3, "oiliness": 1}, (
        "acne 更新做 3，但 oiliness 唔可以被冇提及嘅 0 抹走"
    )
    assert entry.note == "今日下巴爆咗兩粒瘡，T字位好油\n尋晚打邊爐食咗辣底，今朝爆多咗兩粒"
    detail = [t for t in second["trace"] if t["node"] == "persist"][0]["detail"]
    assert detail["attributes_kept"] == ["oiliness"]
    assert detail["insights_strengthened"] == 1, (
        "淨係 acne 呢條記憶應該更新；以前連 oiliness 都用假 0 strengthen"
    )
    assert detail["insights_superseded"] == 0
    oiliness = s.query(Insight).filter_by(conversation_id=cid, tag="oiliness").one()
    assert oiliness.confidence == 0.6 and oiliness.text == "油光：輕微", "冇提及嘅記憶唔應該被掂"
    assert s.query(Insight).filter_by(conversation_id=cid).count() == 2
    s.close()


def test_a_mention_of_improvement_still_flips_the_memory():
    """Policy B must not become "never update a reading". Saying it improved counts."""
    sf = make_factory()
    cid = seed_conversation(sf)
    llm = ScriptedLLM(
        [
            SkinAnalysis(
                observes_skin=True,
                summary="下巴有兩粒",
                attributes=[attr("acne", 2, True)],
            ),
            SkinAnalysis(
                observes_skin=True,
                summary="今日消咗好多",
                attributes=[attr("acne", 0, True)],
            ),
        ]
    )

    run(sf, llm, cid, "下巴爆咗兩粒")
    run(sf, llm, cid, "今日消咗好多")

    s = sf()
    entry = s.query(Entry).filter_by(conversation_id=cid).one()
    assert severity_map(entry.attributes) == {"acne": 0}
    superseded = s.query(Insight).filter_by(conversation_id=cid, tag="acne").all()
    assert len(superseded) == 2, "問題→正常要版本升級，唔係靜靜改舊 row"
    s.close()


def test_a_question_still_writes_nothing_at_all():
    """The existing `observes_skin` gate is untouched by the merge."""
    sf = make_factory()
    cid = seed_conversation(sf)
    llm = ScriptedLLM(
        [
            SkinAnalysis(
                observes_skin=True,
                summary="下巴有兩粒",
                attributes=[attr("acne", 2, True)],
            ),
            SkinAnalysis(observes_skin=False, summary="（未提及皮膚）", attributes=[attr("acne", 0, False)]),
        ]
    )

    run(sf, llm, cid, "下巴爆咗兩粒")
    run(sf, llm, cid, "呢支精華得唔得？")

    s = sf()
    entry = s.query(Entry).filter_by(conversation_id=cid).one()
    assert severity_map(entry.attributes) == {"acne": 2}, "問問題唔可以掂到當日讀數"
    assert s.query(TimelineEvent).filter_by(conversation_id=cid).count() == 0
    assert s.query(ChatMessage).filter_by(conversation_id=cid).count() == 4
    s.close()


def test_an_output_without_the_flag_keeps_the_old_replace_behaviour():
    """Backwards compatible: no `mentioned` key means "the model rated this attribute"."""
    merged, _ = merge_attributes(
        [{"key": "oiliness", "severity": 1, "note": ""}],
        [{"key": "oiliness", "severity": 0, "note": ""}],
    )
    assert severity_map(merged) == {"oiliness": 0}


def test_the_advise_prompt_does_not_leak_the_merge_flag():
    prompt = build_advise_prompt(
        {
            "user_text": "今朝爆多咗兩粒",
            "analysis": {
                "observes_skin": True,
                "summary": "x",
                "attributes": [{"key": "acne", "severity": 1, "note": "", "mentioned": True}],
            },
            "tool_results": [],
            "first_checkin": False,
            "recent_messages": [],
        }
    )
    assert "mentioned" not in prompt, "內部 bookkeeping 唔應該入 prompt（model 會照講返）"
    assert '"severity"' in prompt, "sanity: 分析內容本身仍然要喺 prompt 度"
