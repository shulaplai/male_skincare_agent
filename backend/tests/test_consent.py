"""Photo consent policy.

Two deployments, one code path:

* **self-host / single user (this repo's real one)** — `require_photo_consent=False`
  (default): consent counts as already given, so the gate never blocks the only
  user. A row that predates the switch is backfilled once at startup.
* **hosted / multi user** — `SKINCOACH_REQUIRE_PHOTO_CONSENT=true`: the user has to
  tick the box (frontend `ConsentGate`), and **the server enforces it either way**:
  `service.run_consult` refuses to send an image byte without consent.

Withdrawal is explicit and survives restarts (the backfill only touches rows that
never consented — see `_normalise_consent_policy`).
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import crud
from app.config import settings
from app.db import Base, get_session
from app.models import Conversation, User


@pytest.fixture()
def sf(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'consent.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture()
def client(sf):
    from app.main import app

    def override():
        s = sf()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_self_host_default_is_consent_given(sf):
    s = sf()
    try:
        state = crud.consent_state(s)
        assert state["granted"] is True
        assert state["at"] is not None, "要有時間戳記錄幾時開始同意"
        assert state["required"] is False
    finally:
        s.close()


def test_hosted_deployment_asks_first(sf, monkeypatch):
    monkeypatch.setattr(settings, "require_photo_consent", True)
    s = sf()
    try:
        state = crud.consent_state(s)
        assert state == {"granted": False, "at": None, "required": True}
        assert crud.set_consent(s, True)["granted"] is True  # 用戶打勾之後
    finally:
        s.close()


def test_the_gate_state_is_reported_over_the_api(client):
    body = client.get("/api/consent").json()
    assert body["granted"] is True and body["required"] is False


def test_consent_can_be_withdrawn(client):
    body = client.post("/api/consent", json={"granted": False}).json()
    assert body["granted"] is False
    # 撤回保留 `consent_at`（記錄曾經同意過），但狀態真係變 false
    assert body["at"] is not None
    assert client.get("/api/consent").json()["granted"] is False


def test_backfill_does_not_re_grant_a_withdrawn_consent(sf, monkeypatch):
    """自願撤回之後重啟：唔可以幫佢自動開返。"""
    from app import db as app_db

    s = sf()
    try:
        crud.get_or_create_default_user(s)
        crud.set_consent(s, False)
    finally:
        s.close()

    monkeypatch.setattr(app_db, "engine", sf().get_bind())
    app_db._normalise_consent_policy()

    s = sf()
    try:
        assert crud.consent_state(s)["granted"] is False
    finally:
        s.close()


def test_backfill_grants_a_row_that_never_consented(sf, monkeypatch):
    from app import db as app_db

    s = sf()
    try:
        s.add(User(name="舊 row"))  # photo_cloud_consent=0, consent_at=None
        s.commit()
    finally:
        s.close()

    monkeypatch.setattr(app_db, "engine", sf().get_bind())
    app_db._normalise_consent_policy()

    s = sf()
    try:
        state = crud.consent_state(s)
        assert state["granted"] is True and state["at"] is not None
    finally:
        s.close()


def test_new_conversation_is_always_cloud_analysed(sf, monkeypatch):
    monkeypatch.setenv("SKINCOACH_CLOUD_ANALYSIS_DEFAULT", "false")
    s = sf()
    try:
        assert crud.create_conversation(s, "面部皮膚").cloud_analysis is True
    finally:
        s.close()


def test_per_conversation_toggle_route_is_gone(client, sf):
    s = sf()
    try:
        cid = crud.create_conversation(s, "面部皮膚").id
    finally:
        s.close()
    # 舊 route 已經冇咗（冇咗「本地模式」呢個狀態）→ 冇任何 path 對得上（404）
    r = client.put(f"/api/conversations/{cid}/cloud-analysis", json={"enabled": False})
    assert r.status_code == 404, "per-conversation toggle 唔應該再存在"


def test_run_consult_refuses_vision_without_consent(sf, monkeypatch):
    """The real guarantee: text-only without consent, checked server-side."""
    from app.agent import service

    s = sf()
    try:
        u = User(name="t")
        s.add(u)
        s.commit()
        conv = Conversation(user_id=u.id, body_part="面部皮膚", cloud_analysis=True)
        s.add(conv)
        s.commit()
        cid, uid = conv.id, u.id
    finally:
        s.close()

    seen: dict = {}

    class FakeGraph:
        def invoke(self, state):
            seen.update(state)
            return {"vision_used": False, "trace": []}

    monkeypatch.setattr(service, "build_graph", lambda **kw: FakeGraph())
    monkeypatch.setattr(service, "get_llm", lambda kind="text": object())
    monkeypatch.setattr(service, "SessionLocal", sf)
    monkeypatch.setattr(service, "write_run_log", lambda *a, **k: None)

    service.run_consult(cid, "下巴爆瘡", ["0" * 32])
    assert seen["cloud_analysis"] is False, "未同意就唔可以開 vision"

    s = sf()
    try:
        s.query(User).filter_by(id=uid).first().photo_cloud_consent = True
        s.commit()
    finally:
        s.close()

    service.run_consult(cid, "下巴爆瘡", ["0" * 32])
    assert seen["cloud_analysis"] is True, "同意之後 vision 要開返"
