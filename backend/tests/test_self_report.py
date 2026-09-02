"""Confirmed self-report events -> Entry/timeline/products (Q49/Q51/Q28)."""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.schemas import DetectedEvent
from app.db import Base
from app.models import Conversation, Entry, Product, TimelineEvent, User
from app.self_report import apply_events, trigger_tags


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(sf):
    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
    session.add(c)
    session.commit()
    cid = c.id
    session.close()
    return cid


def test_trigger_tags_deterministic():
    assert "spicy" in trigger_tags("打邊爐食咗辣底")
    assert "sugary" in trigger_tags("食咗件芝士蛋糕")
    assert trigger_tags("食咗白飯") == []


def test_apply_events_writes_entry_timeline_and_product():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    stats = apply_events(
        session,
        cid,
        [
            DetectedEvent(type="diet", text="食咗辣底", tags=["spicy"]),
            DetectedEvent(type="product_start", product_name="水楊酸 Toner", text="開始用：水楊酸 Toner"),
        ],
    )
    assert stats["diet"] == 1
    assert stats["product"] == 1

    entry = session.query(Entry).filter_by(conversation_id=cid).first()
    assert entry is not None
    assert "食咗辣底" in entry.diet
    prod = session.query(Product).filter_by(conversation_id=cid).first()
    assert prod is not None
    assert prod.name == "水楊酸 Toner"
    assert prod.id in entry.products

    events = session.query(TimelineEvent).filter_by(conversation_id=cid, source="user").all()
    texts = {e.text for e in events}
    assert "食咗辣底" in texts
    assert any("水楊酸" in t for t in texts)
    session.close()


def test_apply_events_dedupes_same_day():
    sf = make_factory()
    cid = _seed(sf)
    session = sf()
    ev = DetectedEvent(type="diet", text="食咗辣底")
    apply_events(session, cid, [ev])
    stats = apply_events(session, cid, [ev])
    assert stats["diet"] == 0  # already recorded today
    entry = session.query(Entry).filter_by(conversation_id=cid).first()
    assert entry.diet.count("食咗辣底") == 1
    session.close()
