"""Preference extraction (Q48): deterministic, throttled, evidence-based."""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Conversation, Entry, Insight, Product, TimelineEvent, User
from app.preferences import extract_preferences

D = datetime.date


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(sf, conv_cloud=True):
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=conv_cloud)
    session.add(c)
    session.commit()
    cid = c.id
    session.close()
    return cid


def _today_minus(days: int) -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=days)


def test_diet_preference_after_repeated_days():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    # 3 distinct days of spicy within the window -> global preference.
    for i, days_ago in enumerate((0, 1, 2)):
        session.add(
            TimelineEvent(
                conversation_id=None,
                date=_today_minus(days_ago),
                text="食咗辣底",
                source="user",
            )
        )
    session.commit()
    res = extract_preferences(session, cid)
    assert res["written"] >= 1
    prefs = (
        session.query(Insight)
        .filter_by(kind="preference", conversation_id=None)
        .all()
    )
    assert any("辣" in p.text for p in prefs)
    session.close()


def test_preference_throttled_no_rewrite_same_day():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    for days_ago in (0, 1, 2):
        session.add(
            TimelineEvent(
                conversation_id=None,
                date=_today_minus(days_ago),
                text="食咗辣底",
                source="user",
            )
        )
    session.commit()
    first = extract_preferences(session, cid)["written"]
    second = extract_preferences(session, cid)["written"]
    assert first >= 1
    assert second == 0  # throttled: identical text already present
    session.close()


def test_product_preference_after_three_days():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    p = Product(conversation_id=cid, name="水楊酸 Toner")
    session.add(p)
    session.flush()
    for i in range(3):
        session.add(
            Entry(
                conversation_id=cid,
                date=_today_minus(i),
                attributes=[{"key": "acne", "severity": 1}],
                products=[p.id],
            )
        )
    session.commit()
    res = extract_preferences(session, cid)
    assert res["written"] >= 1
    prefs = (
        session.query(Insight)
        .filter_by(kind="preference", conversation_id=cid)
        .all()
    )
    assert any("水楊酸 Toner" in p.text for p in prefs)
    session.close()


def test_below_threshold_writes_nothing():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    session.add(
        TimelineEvent(
            conversation_id=None,
            date=_today_minus(0),
            text="食咗辣底",
            source="user",
        )
    )
    session.commit()
    res = extract_preferences(session, cid)
    assert res["written"] == 0  # only 1 day < DIET_MIN_DAYS
    session.close()
