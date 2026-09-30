"""API tests for `POST /api/conversations/{cid}/products/evaluate`.

The load-bearing one is `test_evaluate_writes_nothing`: this endpoint must never
touch `Entry`/`Product`. Routing a product question through the consult graph would
upsert today's `Entry`, and change detection / timeline / anchors all diff `Entry`,
so the question would silently become a day of skin data.
"""
import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest

from app.agent.llm import FakeLLM
from app.db import Base, get_session
from app.main import app
from app.models import ChatMessage, Conversation, Entry, Insight, Photo, Product, TimelineEvent, User

D = datetime.date


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch):
    """Keep the endpoint off the network.

    The route builds its own LLM via `get_llm("text")`, and `backend/.env` has a real
    key — so without this the suite would spend real API credit. Patching the name
    `app.main` imported is the correct seam (it holds its own reference).
    """
    monkeypatch.setattr("app.main.get_llm", lambda kind="text": FakeLLM())
    yield


def make_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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

    session = sf()
    u = User(name="阿軒")
    session.add(u)
    session.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    session.add(c)
    session.flush()
    cid = c.id
    # Acne + oiliness at "problem" level so the recommender has something to say.
    session.add(
        Entry(
            conversation_id=cid,
            date=D(2026, 2, 1),
            note="下巴爆瘡，T 字位好油",
            attributes=[
                {"key": "acne", "severity": 2, "note": ""},
                {"key": "oiliness", "severity": 2, "note": ""},
                {"key": "dryness", "severity": 0, "note": ""},
            ],
        )
    )
    session.commit()
    session.close()
    return sf, cid


def counts(sf) -> dict:
    s = sf()
    try:
        return {
            "entries": s.query(Entry).count(),
            "products": s.query(Product).count(),
            "insights": s.query(Insight).count(),
            "messages": s.query(ChatMessage).count(),
            "timeline": s.query(TimelineEvent).count(),
            "photos": s.query(Photo).count(),
        }
    finally:
        s.close()


def test_evaluate_writes_nothing():
    """The whole point: an evaluation is a read, not a record."""
    sf, cid = make_env()
    client = TestClient(app)
    before = counts(sf)

    r = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Salicylic Acid 2%, Niacinamide", "name": "某精華"},
    )

    assert r.status_code == 200
    assert counts(sf) == before, "evaluation must not write Entry/Product/Insight/…"


def test_evaluate_unknown_conversation_is_404():
    sf, _ = make_env()
    client = TestClient(app)
    r = client.post(
        "/api/conversations/does-not-exist/products/evaluate",
        json={"ingredients_text": "Aqua"},
    )
    assert r.status_code == 404


def test_evaluate_good_product_reports_coverage():
    sf, cid = make_env()
    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Salicylic Acid 2%, Niacinamide, Glycerin"},
    ).json()

    assert body["verdict"] == "good"
    assert set(body["matched"]) == {"水楊酸", "菸鹼醯胺"}
    assert body["missing"] == []
    assert body["escalate"] is False
    assert body["disclaimer"]
    # Two tiers are surfaced (D6), primary first.
    tiers = {s["tier"] for s in body["suggestions"]}
    assert tiers == {"primary", "alternative"}
    assert body["suggestions"][0]["tier"] == "primary"


def test_evaluate_prescription_ingredient_avoids_and_escalates():
    sf, cid = make_env()
    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Isotretinoin", "name": "某藥膏"},
    ).json()

    assert body["verdict"] == "avoid"
    assert body["escalate"] is True
    assert body["matched"] == []  # coverage suppressed next to a hard stop
    # FakeLLM must not invent product advice, and escalation skips the narrative.
    assert body["narrative"] is None


def test_evaluate_detects_pigmentation_from_the_users_own_words():
    """D7 option 1: a note keyword, never a 7th attribute."""
    sf, cid = make_env()
    s = sf()
    s.add(
        Entry(
            conversation_id=cid,
            date=D(2026, 2, 2),
            note="下巴爆完瘡留咗好多印，好想搞",
            attributes=[{"key": "acne", "severity": 2, "note": ""}],
        )
    )
    s.commit()
    s.close()

    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Alpha-Arbutin"},
    ).json()

    assert body["pigmentation_source"] == "notes"
    assert "pigmentation" in body["triggers"]
    assert body["verdict"] == "good"


def test_evaluate_pigmentation_can_be_forced_by_the_request():
    """D7 option 2: the explicit override wins over note detection."""
    sf, cid = make_env()
    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Alpha-Arbutin", "pigmentation": True},
    ).json()

    assert body["pigmentation_source"] == "request"
    assert "pigmentation" in body["triggers"]


def test_evaluate_notices_the_user_already_uses_the_same_active():
    """The products table is empty in practice, so the active is read off the name."""
    sf, cid = make_env()
    s = sf()
    s.add(Product(conversation_id=cid, name="水楊酸 toner"))
    s.commit()
    s.close()

    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Salicylic Acid 2%, Niacinamide"},
    ).json()

    assert body["verdict"] == "caution"
    kinds = {c["kind"] for c in body["conflicts"]}
    assert "duplicate_active" in kinds
    assert any("水楊酸 toner" in c["text"] for c in body["conflicts"])


def test_evaluate_with_no_entries_yet_is_insufficient_info_not_a_crash():
    """A brand-new conversation has no profile to compare against."""
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
    s = sf()
    u = User(name="新用戶")
    s.add(u)
    s.flush()
    c = Conversation(user_id=u.id, body_part="面部皮膚")
    s.add(c)
    s.commit()
    cid = c.id
    s.close()

    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Glycerin"},
    ).json()

    assert body["triggers"] == []
    assert body["suggestions"] == []
    assert body["verdict"] in ("insufficient_info", "caution")


def test_evaluate_does_not_reach_for_a_real_llm_without_a_key():
    """FakeLLM must never fabricate a product narrative."""
    sf, cid = make_env()
    client = TestClient(app)
    body = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": "Aqua, Salicylic Acid 2%, Niacinamide"},
    ).json()
    assert body["verdict"] == "good"
    assert body["narrative"] is None


def test_the_route_and_the_chat_path_agree():
    """One definition of the inputs, two callers.

    `POST /products/evaluate` and a pasted list in chat both go through
    `product_context.profile_inputs`, so the verdict cannot depend on which door the
    user came in. This is the same defect class as the guardrail that scanned `items`
    in one place and `reply` in another: two implementations, one blind spot between
    them. Compared on the deterministic fields only — `narrative` is presentation.
    """
    from app.agent.product_context import evaluate_for_conversation, summarise_evaluation

    sf, cid = make_env()
    client = TestClient(app)
    text = "Aqua, Salicylic Acid 2%, Niacinamide, Glycerin, Panthenol, Allantoin"

    via_route = client.post(
        f"/api/conversations/{cid}/products/evaluate",
        json={"ingredients_text": text, "name": "某精華"},
    ).json()

    s = sf()
    via_context = summarise_evaluation(evaluate_for_conversation(s, cid, text))
    s.close()

    for field in ("verdict", "recognised", "unknown", "matched", "missing", "triggers", "escalate"):
        assert via_route[field] == via_context[field], f"{field} differs between the two doors"
    assert via_route["conflicts"] == via_context["conflicts"]
