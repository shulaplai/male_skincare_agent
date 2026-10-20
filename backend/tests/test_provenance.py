"""Issue #14: every consult records HOW it was produced, and `vision_used` is honest.

Decision (a), full provenance: the resolved adapter/model + live-vs-fake mode is
persisted on the coach `ChatMessage` (a real column, so it survives reload and is
queryable per turn), returned by the messages API, shown as a chip, and written to
the run log. These tests pin the three falsehoods from the ticket:

1. a FakeLLM turn must be stored as fake, not as if a real model wrote it;
2. `/health` / `/api/settings` report the RESOLVED adapter, so a silent fallback
   to FakeLLM cannot hide behind the configured provider name;
3. `vision_used=None` (unknown) must not become `False` (which the UI renders as
   「文字分析（未睇相）」).
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import service
from app.agent.graph import build_graph as real_build_graph
from app.agent.llm import FakeLLM, LLMProvenance
from app.config import settings
from app.db import Base, get_session
from app.main import app
from app.models import ChatMessage, Conversation, User
from app.rag import DeterministicEmbedder


class FakeLiveLLM(FakeLLM):
    """Deterministic like FakeLLM, but its adapter claims to be the live OpenAI one.

    This lets a test drive the real graph without any network and still prove the
    persistence path stores the *resolved* provider/adapter/model it was given.
    """

    provider = "openai"
    provenance = LLMProvenance(
        mode="live", provider="openai", adapter="OpenAICompatLLM", model="gpt-4o-mini"
    )


@pytest.fixture
def env(monkeypatch):
    """Throwaway DB shared by `service` and the API, plus one conversation."""
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

    session = sf()
    user = User(name="阿軒")
    session.add(user)
    session.flush()
    user.photo_cloud_consent = True
    conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
    session.add(conv)
    session.commit()
    cid = conv.id
    session.close()

    monkeypatch.setattr(service, "SessionLocal", sf)
    monkeypatch.setattr(service, "_get_embedder", lambda: DeterministicEmbedder())
    monkeypatch.setattr(settings, "run_log_enabled", False)
    try:
        yield sf, cid
    finally:
        app.dependency_overrides.clear()


def wire(monkeypatch, sf, llm):
    """Point the resolver at `llm` and build the REAL graph around it (no network)."""

    def _build(**kwargs):
        return real_build_graph(
            llm=llm, vision_llm=llm, session_factory=sf, embedder=DeterministicEmbedder()
        )

    monkeypatch.setattr(service, "build_graph", _build)
    monkeypatch.setattr(service, "get_llm", lambda kind="text": llm)


def test_fake_turn_persists_mode_fake_and_messages_api_returns_it(env, monkeypatch):
    sf, cid = env
    wire(monkeypatch, sf, FakeLLM())
    client = TestClient(app)

    r = client.post("/api/consult", json={"conversation_id": cid, "text": "下巴爆瘡"})
    assert r.status_code == 200, r.text
    assert r.json()["provenance"]["mode"] == "fake"

    msgs = client.get(f"/api/conversations/{cid}/messages").json()
    coach = [m for m in msgs if m["role"] == "coach"][-1]
    assert coach["provenance"] == {
        "mode": "fake",
        "provider": "fake",
        "adapter": "FakeLLM",
        "model": "",
        "vision": {
            "mode": "fake",
            "provider": "fake",
            "adapter": "FakeLLM",
            "model": "",
        },
    }, "messages API 要回 chip 用嘅 provenance，reload 之後都仲喺度"

    session = sf()
    try:
        row = session.query(ChatMessage).filter_by(conversation_id=cid, role="coach").one()
    finally:
        session.close()
    assert row.provenance["mode"] == "fake", "column 要有真值，唔係得 API 砌出嚟"


def test_live_resolved_turn_persists_adapter_and_model(env, monkeypatch):
    sf, cid = env
    wire(monkeypatch, sf, FakeLiveLLM())
    client = TestClient(app)

    r = client.post("/api/consult", json={"conversation_id": cid, "text": "下巴爆瘡"})
    assert r.status_code == 200, r.text

    coach = [m for m in client.get(f"/api/conversations/{cid}/messages").json() if m["role"] == "coach"][-1]
    prov = coach["provenance"]
    assert prov["mode"] == "live"
    assert prov["provider"] == "openai"
    assert prov["adapter"] == "OpenAICompatLLM"
    assert prov["model"] == "gpt-4o-mini"
    # The photo adapter is resolved separately (`get_llm("vision")`), so it gets
    # its own record instead of pretending the text model saw the photo.
    assert prov["vision"]["model"] == "gpt-4o-mini"


def test_get_llm_reports_the_resolved_provider_and_model(monkeypatch):
    """The record comes from the adapter itself — no second provider-name switch."""
    from app.agent.llm import get_llm

    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "sk-test-not-used")

    for kind, expected_model in (
        ("text", settings.deepseek_text_model),
        ("vision", settings.deepseek_vision_model),
    ):
        prov = get_llm(kind).provenance
        assert (prov.mode, prov.provider, prov.adapter, prov.model) == (
            "live",
            "deepseek",
            "OpenAICompatLLM",
            expected_model,
        )


def test_health_and_settings_report_resolved_fallback(monkeypatch):
    """Configured deepseek + no key resolves to FakeLLM; the endpoints must say so."""
    monkeypatch.setattr(settings, "llm_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "openai_api_key", "")
    client = TestClient(app)

    health = client.get("/health").json()
    assert health["configured_provider"] == "deepseek"
    assert health["llm_provider"] == "fake", "唔可以報 configured provider"
    assert health["llm_mode"] == "fake"
    assert health["llm_adapter"] == "FakeLLM"

    s = client.get("/api/settings").json()
    assert s["configured_provider"] == "deepseek"
    assert s["llm_provider"] == "fake"
    assert s["llm_mode"] == "fake"
    assert s["llm_adapter"] == "FakeLLM"
    assert s["model"] == ""  # FakeLLM has no model id — honesty over a pretty cell


def test_unknown_vision_does_not_become_false(monkeypatch, tmp_path):
    """`_finish_consult` + the run log keep the three states apart."""
    monkeypatch.setattr(settings, "run_log_enabled", True)
    monkeypatch.setattr(settings, "run_log_path", str(tmp_path / "runs.jsonl"))

    unknown = service._finish_consult("c", "hi", {"provenance": {"mode": "fake"}})
    assert unknown["vision_used"] is None, "未知唔可以降級成『未睇相』"

    false = service._finish_consult("c", "hi", {"vision_used": False})
    assert false["vision_used"] is False
    true = service._finish_consult("c", "hi", {"vision_used": True})
    assert true["vision_used"] is True

    lines = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text().splitlines()]
    assert lines[0]["vision_used"] is None
    assert lines[0]["llm_mode"] == "fake", "run log 要記低今次係 fake"
    assert lines[2]["vision_used"] is True


def test_unknown_vision_survives_the_messages_api_round_trip(env):
    sf, cid = env
    session = sf()
    session.add(
        ChatMessage(
            conversation_id=cid,
            role="coach",
            text="舊訊息",
            payload={"summary": "舊", "reply": "舊", "vision_used": None},
            provenance={"mode": "fake", "provider": "fake", "adapter": "FakeLLM", "model": ""},
        )
    )
    session.commit()
    session.close()

    msg = TestClient(app).get(f"/api/conversations/{cid}/messages").json()[-1]
    assert msg["payload"]["vision_used"] is None
    assert msg["provenance"]["adapter"] == "FakeLLM"
