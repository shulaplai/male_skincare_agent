"""Observability / debuggability guarantees.

These lock in the things that made "the reply looks wrong" hard to debug:
- the model is actually told which tools exist (prompt + schema + whitelist agree);
- every node leaves a trace entry with its own summary;
- failures (bad tool name, tool exception, vision exception) are recorded, not swallowed;
- embedding dimensions can never be silently mixed (128-dim fallback vs 384-dim real).
"""
import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent.graph import build_graph
from app.agent.llm import FakeLLM
from app.agent.prompts import ANALYZE_SYSTEM, TOOL_GUIDE
from app.agent.schemas import SkinAnalysis
from app.agent.tools import WHITELIST
from app.db import Base
from app.models import Conversation, Insight, User
from app.rag import DeterministicEmbedder
from app.rag.ingest import ingest_text
from app.rag.vectorstore import ChunkItem, add_chunks, existing_dim

KNOWLEDGE = "油性皮膚需要溫和清潔同控油，避免過度去角質；暗瘡唔好擠壓，做好保濕同防曬。"


def make_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def seed(sf, embedder, *, with_knowledge=True, cloud=False):
    session = sf()
    user = User(name="obs")
    session.add(user)
    session.flush()
    conv = Conversation(user_id=user.id, body_part="面部皮膚", icon="🧔", cloud_analysis=cloud)
    session.add(conv)
    session.commit()
    cid = conv.id
    if with_knowledge:
        ingest_text(session, "seed", KNOWLEDGE, embedder)
    session.close()
    return cid


def run(sf, embedder, cid, *, tool_override=None, vision_llm=None, text="下巴爆瘡好油，點算？", photos=()):
    """Run the graph, optionally with a FakeLLM whose tool_calls we control."""
    llm = FakeLLM()
    if tool_override is not None:
        original = llm.structured

        def patched(system, user, schema):
            out = original(system, user, schema)
            if schema is SkinAnalysis:
                out.tool_calls = list(tool_override)
            return out

        llm.structured = patched  # type: ignore[method-assign]
    graph = build_graph(llm=llm, vision_llm=vision_llm or FakeLLM(), session_factory=sf, embedder=embedder)
    return graph.invoke(
        {
            "conversation_id": cid,
            "user_text": text,
            "photo_paths": list(photos),
            "cloud_analysis": bool(vision_llm),
            "trace": [],
        }
    )


# ---------- 1. tool names must be discoverable by the model ----------


def test_tool_guide_lists_every_whitelisted_tool():
    bullets = [line for line in TOOL_GUIDE.splitlines() if line.startswith("- `")]
    documented = {m for line in bullets for m in re.findall(r"`([a-z_]+)`", line)}
    assert documented == WHITELIST, f"prompt 講嘅 tool {documented} ≠ whitelist {WHITELIST}"


def test_analyze_system_prompt_includes_tool_guide():
    for name in WHITELIST:
        assert name in ANALYZE_SYSTEM


def test_tool_calls_field_is_described_with_valid_names():
    desc = SkinAnalysis.model_fields["tool_calls"].description or ""
    for name in WHITELIST:
        assert name in desc


def test_fakellm_only_proposes_whitelisted_tools():
    analysis = FakeLLM().structured("s", "u", SkinAnalysis)
    assert set(analysis.tool_calls) <= WHITELIST


# ---------- 2. trace ----------


def test_trace_records_every_node_in_order():
    sf, embedder = make_factory(), DeterministicEmbedder()
    cid = seed(sf, embedder)
    result = run(sf, embedder, cid)

    nodes = [t["node"] for t in result["trace"]]
    assert nodes == ["analyze", "tools", "advise", "guardrail", "persist"]

    by_node = {t["node"]: t["detail"] for t in result["trace"]}
    assert by_node["analyze"]["tool_calls"] == ["get_skin_profile", "search_knowledge"]
    assert by_node["analyze"]["vision_used"] is False
    assert by_node["tools"]["ran"][1]["tool"] == "search_knowledge"
    assert by_node["tools"]["ran"][1]["rows"] == 1  # 知識有真係檢索到
    assert by_node["advise"]["tool_rows"] == 1  # 檢索結果真係入咗 prompt
    assert by_node["advise"]["prompt_chars"] > 0
    assert by_node["guardrail"]["escalate"] is False
    assert by_node["persist"]["insights_created"] == 3  # FakeLLM 出 3 個 attributes
    assert all(t["ms"] >= 0 for t in result["trace"])


def test_trace_flags_unknown_tool_and_keeps_going():
    sf, embedder = make_factory(), DeterministicEmbedder()
    cid = seed(sf, embedder)
    result = run(sf, embedder, cid, tool_override=["search_knowledge", "retrieve_beauty_kb"])

    ran = {r["tool"]: r for r in result["tool_results"]}
    assert "unknown tool" in (ran["retrieve_beauty_kb"]["error"] or "")
    assert ran["search_knowledge"].get("error") is None
    tools_detail = next(t["detail"] for t in result["trace"] if t["node"] == "tools")
    assert tools_detail["requested"] == ["search_knowledge", "retrieve_beauty_kb"]
    # 唔會因為一個假 tool 名而炸掉整個 consult
    assert result["advice"]["items"]


def test_trace_flags_tool_exception(monkeypatch):
    sf, embedder = make_factory(), DeterministicEmbedder()
    cid = seed(sf, embedder)

    import app.agent.graph as graph_mod

    def boom(name, state, session, embedder):  # noqa: ARG001
        raise RuntimeError("db exploded")

    monkeypatch.setattr(graph_mod, "run_tool", boom)
    result = run(sf, embedder, cid, tool_override=["search_knowledge"])

    ran = result["tool_results"][0]
    assert ran["result"] is None
    assert "db exploded" in (ran["error"] or "")
    tools_detail = next(t["detail"] for t in result["trace"] if t["node"] == "tools")
    assert "db exploded" in tools_detail["ran"][0]["error"]


def test_trace_records_vision_failure_instead_of_swallowing(monkeypatch):
    """vision 爆嘅時候要降級做純文字，但一定要留痕（之前係靜靜吞咗）。"""
    sf, embedder = make_factory(), DeterministicEmbedder()
    cid = seed(sf, embedder)

    import app.agent.graph as graph_mod

    monkeypatch.setattr(graph_mod, "load_photo_b64", lambda pid: {"media_type": "image/jpeg", "data": "x"})

    class BoomVision:
        """唔可以繼承 FakeLLM：graph 見到 FakeLLM 就唔會當佢係真 vision model。"""

        def structured_vision(self, *a, **kw):
            raise RuntimeError("vision 503")

    result = run(sf, embedder, cid, vision_llm=BoomVision(), text="睇下我塊面", photos=["a" * 32])
    detail = next(t["detail"] for t in result["trace"] if t["node"] == "analyze")
    assert detail["vision_attempted"] is True
    assert detail["vision_used"] is False
    assert "vision 503" in (detail["vision_error"] or "")
    assert result["analysis"]["summary"]  # 仍然有純文字分析結果


def test_persist_trace_reports_writes():
    sf, embedder = make_factory(), DeterministicEmbedder()
    cid = seed(sf, embedder)
    result = run(sf, embedder, cid)
    detail = next(t["detail"] for t in result["trace"] if t["node"] == "persist")
    assert detail["entry_reused"] is False
    assert detail["attributes"] == 3
    assert detail["insights_created"] == 3

    # 同一日再跑一次：entry 要被 reuse、insight 要被 strengthen（唔係再開新）
    again = run(sf, embedder, cid)
    detail2 = next(t["detail"] for t in again["trace"] if t["node"] == "persist")
    assert detail2["entry_reused"] is True
    assert detail2["insights_strengthened"] == 3
    assert detail2["insights_created"] == 0


# ---------- 3. embedding dimension guard ----------


def test_add_chunks_refuses_mixed_embedding_dimensions():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine)
    session = sf()
    add_chunks(session, [ChunkItem(text="a", embedding=[0.1] * 384)])
    assert existing_dim(session) == 384
    with pytest.raises(ValueError, match="維度唔一致"):
        add_chunks(session, [ChunkItem(text="b", embedding=[0.1] * 128)])
    session.close()


def test_search_skips_chunks_with_mismatched_dimensions():
    from app.rag.vectorstore import search

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    add_chunks(
        session,
        [
            ChunkItem(text="right", embedding=[1.0, 0.0, 0.0]),
            ChunkItem(text="wrong", embedding=[1.0, 0.0]),  # 唔同維度，唔應該被比較
        ],
    )
    hits = search(session, [1.0, 0.0, 0.0], top_k=5)
    assert [c.text for c, _ in hits] == ["right"]
    session.close()


# ---------- 4. run log ----------


def test_run_log_is_written_and_contains_trace(tmp_path, monkeypatch):
    from app.agent import service
    from app.config import settings

    monkeypatch.setattr(settings, "run_log_enabled", True)
    monkeypatch.setattr(settings, "run_log_path", str(tmp_path / "runs.jsonl"))
    service.write_run_log("cid-x", "下巴爆瘡", {"vision_used": False, "escalate": False, "trace": [{"node": "analyze"}]})

    lines = (tmp_path / "runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    import json

    record = json.loads(lines[0])
    assert record["conversation_id"] == "cid-x"
    assert record["trace"][0]["node"] == "analyze"


def test_run_log_failure_never_raises(monkeypatch):
    from app.agent import service
    from app.config import settings

    monkeypatch.setattr(settings, "run_log_enabled", True)
    monkeypatch.setattr(settings, "run_log_path", "/proc/definitely/not/writable.jsonl")
    service.write_run_log("cid", "text", {})  # 唔應該拋 exception
