"""Correlation detector (Q30): deterministic candidates over plain data + DB."""
import datetime

from app.correlation import conversation_candidates, detect_candidates

D = datetime.date


def day(y, m, dd):
    return D(y, m, dd)


def test_detect_candidates_repeated_episode_marks_strong():
    entries = [
        {"date": day(2026, 1, 1), "attrs": {"acne": 1, "redness": 1}},
        {"date": day(2026, 1, 3), "attrs": {"acne": 2, "redness": 1}},  # after spicy #1
        {"date": day(2026, 1, 6), "attrs": {"acne": 2, "redness": 1}},
        {"date": day(2026, 1, 10), "attrs": {"acne": 1, "redness": 1}},
        {"date": day(2026, 1, 12), "attrs": {"acne": 2, "redness": 1}},  # after spicy #2
        {"date": day(2026, 1, 16), "attrs": {"acne": 1, "redness": 1}},
        {"date": day(2026, 1, 20), "attrs": {"acne": 2, "redness": 1}},  # after spicy #3
    ]
    causes = [
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 2)},
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 11)},
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 19)},
    ]
    cands = detect_candidates(entries, causes)
    assert cands, "expected at least one candidate"
    top = cands[0]
    assert top["cause_label"] == "辣嘢"
    assert top["attribute"] == "acne"
    assert top["direction"] == "up"
    assert top["occurrences"] == 3
    assert top["strong"] is True
    # Deterministic zh explainer present.
    assert top["note"].startswith("「辣嘢」之後 暗瘡 差咗")


def test_detect_candidates_single_observation_not_strong():
    entries = [
        {"date": day(2026, 1, 1), "attrs": {"redness": 1}},
        {"date": day(2026, 1, 5), "attrs": {"redness": 2}},
    ]
    causes = [
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 3)},
    ]
    cands = detect_candidates(entries, causes)
    assert cands
    assert cands[0]["occurrences"] == 1
    assert cands[0]["strong"] is False
    assert "未夠證據" in cands[0]["note"]


def test_detect_clusters_close_episodes():
    """Two diet events 1 day apart are ONE episode (no double counting)."""
    entries = [
        {"date": day(2026, 1, 1), "attrs": {"acne": 1}},
        {"date": day(2026, 1, 4), "attrs": {"acne": 2}},
        {"date": day(2026, 1, 6), "attrs": {"acne": 2}},
    ]
    causes = [
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 2)},
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 3)},
    ]
    cands = detect_candidates(entries, causes)
    assert cands[0]["occurrences"] == 1  # clustered into one episode


def test_detect_needs_baseline_before_cause():
    """No baseline entry before the cause -> nothing can be concluded."""
    entries = [
        {"date": day(2026, 1, 5), "attrs": {"acne": 2}},  # only AFTER cause
    ]
    causes = [
        {"type": "diet", "key": "diet:spicy", "label": "辣嘢", "date": day(2026, 1, 2)},
    ]
    assert detect_candidates(entries, causes) == []


def _seed_conv(sf):
    session = sf()
    from app.models import Conversation, User

    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
    session.add(c)
    session.commit()
    cid = c.id
    session.close()
    return cid


def test_conversation_candidates_db_path():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from app.models import Entry, Product

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    cid = _seed_conv(sf)

    session = sf()
    session.add(Entry(conversation_id=cid, date=day(2026, 1, 1), attributes=[{"key": "redness", "severity": 1}]))
    p = Product(conversation_id=cid, name="水楊酸 Toner")
    session.add(p)
    session.flush()
    session.add(
        Entry(
            conversation_id=cid,
            date=day(2026, 1, 5),
            attributes=[{"key": "redness", "severity": 2}],
            products=[p.id],
        )
    )
    session.add(
        Entry(
            conversation_id=cid,
            date=day(2026, 1, 8),
            attributes=[{"key": "redness", "severity": 2}],
            products=[p.id],
        )
    )
    session.commit()
    session.close()

    session = sf()
    res = conversation_candidates(session, cid)
    session.close()
    assert res["entry_days"] == 3
    # Product first-use (1/5) with a baseline (1/1, redness 1) and follow-ups
    # (1/8 redness 2) -> candidate pointing at redness worsening.
    assert any(
        c["cause_type"] == "product" and c["attribute"] == "redness" and c["direction"] == "up"
        for c in res["candidates"]
    )
