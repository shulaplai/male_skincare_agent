"""`POST /api/consult/stream`: the same consult, reported one node at a time (audit §7).

Measured before this existed: the reply arrived in one lump after a median 5.46 s (slowest
7.36 s), so the UI could only say 「約 5–10 秒」 and then nothing happened. The graph already
walks analyze → tools → advise → guardrail → persist, so the route now emits one SSE frame
per finished node and a final `result` frame carrying exactly what the plain POST returns.

The tests pin the four things that could quietly go wrong:

* every node is named, in order, then the result (the streaming path must not skip a node);
* the streamed result equals the plain route's result (one pipeline, two transports);
* an unknown conversation is a real 404 — **not** a 200 stream that reports the error later
  (the status is already on the wire once the first byte is written, so the check has to
  happen before the response starts);
* a parse failure arrives as an in-band `error` frame with the same sentence the plain
  route puts in its 503 body — a client that only reads the stream still learns the truth.
"""
import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.exceptions import OutputParserException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent import service
from app.agent.graph import build_graph as real_build_graph
from app.agent.llm import FakeLLM
from app.config import settings
from app.db import Base
from app.main import app
from app.models import Conversation, User
from app.rag import DeterministicEmbedder


def seed_conversation(sf) -> str:
    s = sf()
    user = User(name="阿軒")
    s.add(user)
    s.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚", cloud_analysis=True)
    s.add(conv)
    s.commit()
    cid = conv.id
    s.close()
    return cid


@pytest.fixture
def api(tmp_path, monkeypatch):
    """TestClient wired to a throwaway DB and a deterministic FakeLLM graph."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)

    monkeypatch.setattr(service, "SessionLocal", sf)
    monkeypatch.setattr(
        service,
        "build_graph",
        lambda **kw: real_build_graph(
            llm=FakeLLM(),
            vision_llm=FakeLLM(),
            session_factory=sf,
            embedder=DeterministicEmbedder(),
        ),
    )
    # The debug trail must survive the new transport — so the real writer runs, into tmp_path.
    monkeypatch.setattr(settings, "run_log_enabled", True)
    monkeypatch.setattr(settings, "run_log_path", str(tmp_path / "runs.jsonl"))
    try:
        yield TestClient(app), sf, tmp_path
    finally:
        pass


def frames(res) -> list[dict]:
    """Parse SSE frames: one JSON object per `data:` line, frames separated by a blank line."""
    out = []
    for block in res.text.split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            out.append(json.loads(line[len("data:") :].strip()))
    return out


def test_the_stream_names_every_node_in_order_then_the_result(api):
    client, sf, _ = api
    cid = seed_conversation(sf)

    res = client.post("/api/consult/stream", json={"conversation_id": cid, "text": "下巴爆咗兩粒瘡"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")

    got = frames(res)
    assert [f["type"] for f in got] == ["node"] * 5 + ["result"], got
    assert [f["node"] for f in got[:5]] == ["analyze", "tools", "advise", "guardrail", "persist"]

    result = got[-1]
    assert result["analysis"]["summary"]
    assert "advice" in result and "escalate" in result and "vision_used" in result
    assert result["trace"], "trace 要照樣返俾前端（debug 路線唔可以喺串流路徑斷）"


def test_each_node_frame_carries_its_own_ms(api):
    """The UI wants to say 「分析用咗 2.5 秒」, so the per-node ms has to survive."""
    client, sf, _ = api
    cid = seed_conversation(sf)

    got = frames(client.post("/api/consult/stream", json={"conversation_id": cid, "text": "今日好油"}))
    for frame in got[:5]:
        assert isinstance(frame["ms"], (int, float)), frame


def test_the_streamed_result_matches_the_plain_route(api):
    """One pipeline, two transports: the SSE result is not a second implementation."""
    client, sf, _ = api
    streamed = frames(
        client.post("/api/consult/stream", json={"conversation_id": seed_conversation(sf), "text": "下巴爆瘡"})
    )[-1]
    plain = client.post("/api/consult", json={"conversation_id": seed_conversation(sf), "text": "下巴爆瘡"}).json()

    assert streamed["analysis"] == plain["analysis"]
    assert streamed["advice"] == plain["advice"]
    assert streamed["escalate"] == plain["escalate"]
    assert streamed["vision_used"] == plain["vision_used"]


def test_an_unknown_conversation_is_a_real_404_not_a_stream(api):
    client, _, _ = api
    res = client.post("/api/consult/stream", json={"conversation_id": "nope", "text": "hi"})
    assert res.status_code == 404, res.text
    assert "event-stream" not in res.headers["content-type"]


def test_a_parse_failure_arrives_as_an_in_band_error_frame(api, monkeypatch):
    """After the first byte the status is fixed, so the failure has to be said in the stream."""
    client, sf, _ = api
    cid = seed_conversation(sf)

    class ExplodingGraph:
        def stream(self, *a, **kw):
            raise OutputParserException("model kept answering in the wrong shape")

    monkeypatch.setattr(service, "build_graph", lambda **kw: ExplodingGraph())

    res = client.post("/api/consult/stream", json={"conversation_id": cid, "text": "下巴爆瘡"})
    assert res.status_code == 200, "header 已經送咗，唔可以再改 status"
    got = frames(res)
    assert [f["type"] for f in got] == ["error"], got
    assert got[0]["detail"] == service.CONSULT_PARSE_FAILED


def test_the_streaming_path_still_writes_the_run_log(api):
    """A debug trail that only exists on the old transport is a trail that goes missing."""
    client, sf, tmp_path = api
    cid = seed_conversation(sf)

    client.post("/api/consult/stream", json={"conversation_id": cid, "text": "下巴爆瘡"})

    lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, lines
    record = json.loads(lines[0])
    assert record["conversation_id"] == cid
    assert record["user_text"] == "下巴爆瘡"
    assert record["trace"], "run log 要有逐 node trace"
