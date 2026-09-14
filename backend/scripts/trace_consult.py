"""Trace one consult end-to-end — the debugging entry point.

Runs the real 5-node graph and prints what EVERY node did (duration + a small
summary), then dumps what got written to the DB. Use it when a reply looks
wrong: the trace tells you which stage produced the bad state.

    # 最快、最安全（temp DB + FakeLLM，零 API 費用、零真 data 風險）
    ./.venv/bin/python scripts/trace_consult.py --text "下巴爆瘡，T字位好油，點算？"

    # 用真 LLM（讀 backend/.env 嘅 key）—— 驗 tool_calls / vision 呢類「model 行為」
    ./.venv/bin/python scripts/trace_consult.py --real --text "酒糟鼻點護理？"

    # 對住你真 DB 嘅某個 conversation（會寫入真 data！先 copy DB 再玩）
    ./.venv/bin/python scripts/trace_consult.py --db dev --conversation <cid> --real

讀 trace 嘅口訣：
    analyze.tool_calls 空      → model 冇要求工具（RAG/記憶唔會跑）
    tools.ran[].rows = 0       → 工具跑咗但冇資料（chunks 空／維度唔夾）
    tools.ran[].error          → tool 爆咗或者名唔喺 whitelist
    advise.prompt_chars/tool_rows → 檢索結果有冇真係入到 prompt
    guardrail.escalate         → 係唔係轉介（同 quote 邊條規則）
    persist.*                  → 寫咗幾多 attributes／insights／timeline
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.agent.graph import build_graph  # noqa: E402
from app.agent import service
from app.agent.llm import FakeLLM, get_llm  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import ChatMessage, Conversation, Entry, Insight, TimelineEvent, User  # noqa: E402
from app.rag import DeterministicEmbedder, FastembedEmbedder, ingest_text  # noqa: E402

SEED_KNOWLEDGE = (
    "油性皮膚容易出油，需要溫和清潔同控油，避免過度去角質。"
    "暗瘡護理重點係唔好擠壓，做好保濕同每日防曬。"
)


def build_target(args):
    """Return (session_factory, embedder, conversation_id, cleanup_path)."""
    if args.db == "temp":
        tmp = tempfile.NamedTemporaryFile(prefix="skincoach_trace_", suffix=".db", delete=False)
        engine = create_engine(f"sqlite:///{tmp.name}")
        Base.metadata.create_all(engine)
        sf = sessionmaker(bind=engine)
        embedder = DeterministicEmbedder()
        session = sf()
        user = User(name="trace")
        session.add(user)
        session.flush()
        conv = Conversation(user_id=user.id, body_part="面部皮膚", icon="🧔", cloud_analysis=args.cloud)
        session.add(conv)
        session.commit()
        cid = conv.id  # 喺 session 仲生嘅時候攞定（commit 會 expire attributes）
        ingest_text(session, "seed", SEED_KNOWLEDGE, embedder)  # 令 search_knowledge 有嘢回
        session.close()
        return sf, embedder, cid, tmp.name

    # 真 DB（dev 或者指定路徑）：warning —— 會寫入真 data
    db_path = settings.database_url.replace("sqlite:///", "") if args.db == "dev" else args.db
    if not os.path.exists(db_path):
        raise SystemExit(f"DB 唔存在：{db_path}")
    print(f"⚠️  用真 DB：{db_path}（會寫入 Entry/Insight/Timeline/ChatMessage）")
    engine = create_engine(f"sqlite:///{db_path}")
    sf = sessionmaker(bind=engine)
    # 真 DB 嘅 chunks 通常係 384 維 → 一定要用真 embedder，唔係全部 chunk 會被跳過
    embedder = FastembedEmbedder(cache_dir=settings.embedder_cache_dir or None)
    session = sf()
    if args.conversation:
        cid = args.conversation
        if session.query(Conversation).filter_by(id=cid).first() is None:
            raise SystemExit(f"conversation 唔存在：{cid}")
    else:
        conv = session.query(Conversation).first()
        if conv is None:
            raise SystemExit("DB 內冇 conversation，請用 --conversation 或者先開一個")
        cid = conv.id
    session.close()
    return sf, embedder, cid, None


def main() -> None:
    ap = argparse.ArgumentParser(description="Trace one consult through the agent graph")
    ap.add_argument("--text", default="下巴爆瘡，T字位好油，點算？", help="用戶訊息")
    ap.add_argument("--real", action="store_true", help="用真 LLM（讀 backend/.env）；預設 FakeLLM")
    ap.add_argument("--db", default="temp", help="temp（預設，安全）| dev | 指定 .db 路徑")
    ap.add_argument("--conversation", default="", help="用邊個 conversation id（--db dev/指定路徑 先有效）")
    ap.add_argument("--cloud", action="store_true", help="temp DB 時模擬已開雲分析")
    ap.add_argument("--photo", action="append", default=[], help="photo id（可多次；要真存在先會被分析）")
    ap.add_argument("--json", action="store_true", help="只印最終 state 嘅 JSON（唔印逐步 trace）")
    args = ap.parse_args()

    sf, embedder, cid, cleanup = build_target(args)
    llm = get_llm("text") if args.real else FakeLLM()
    vision = get_llm("vision") if args.real else FakeLLM()
    print(f"LLM: {type(llm).__name__} / vision: {type(vision).__name__} | embedder: {type(embedder).__name__}")
    print(f"conversation: {cid}\nuser_text: {args.text}\n")

    graph = build_graph(llm=llm, vision_llm=vision, session_factory=sf, embedder=embedder)
    state = {
        "conversation_id": cid,
        "user_text": args.text,
        "photo_paths": args.photo,
        "cloud_analysis": args.cloud,
        "trace": [],
    }

    final: dict = {}
    trace_steps: list = []
    for step in graph.stream(state):
        for node, delta in step.items():
            if not delta:
                print(f"▸ {node}")
                continue
            final.update({k: v for k, v in delta.items() if k != "trace"})
            trace_steps.extend(delta.get("trace", []))
            for t in delta.get("trace", []):
                print(f"▸ {t['node']}  ({t['ms']} ms)")
                print(f"    {json.dumps(t['detail'], ensure_ascii=False)}")

    if args.json:
        print(json.dumps(final, ensure_ascii=False, indent=2))

    # The run log used to be reachable only via POST /api/consult, which made the
    # documented debug flow ("trace_consult.py …；data/runs.jsonl 有紀錄") false —
    # this CLI builds the graph itself and never went through service.run_consult.
    service.write_run_log(cid, args.text, {**final, "trace": trace_steps})
    print(f"\nrun log: {settings.run_log_path}")

    print("\n──────── 呢次 run 寫咗落 DB ────────")
    session = sf()
    for e in session.query(Entry).filter_by(conversation_id=cid).order_by(Entry.date.desc()).limit(3):
        print(f"Entry {e.date}: attributes={len(e.attributes or [])} diet={e.diet} products={e.products}")
        print(f"  note: {e.note[:60]}")
    for i in session.query(Insight).filter_by(conversation_id=cid).limit(8):
        print(f"Insight [{i.kind}/{i.tag}/{i.direction}] conf={i.confidence} v{i.version}: {i.text}")
    for t in session.query(TimelineEvent).filter_by(conversation_id=cid).limit(5):
        print(f"Timeline {t.date} [{t.source}] {t.text}")
    for m in session.query(ChatMessage).filter_by(conversation_id=cid).order_by(ChatMessage.id.desc()).limit(2):
        print(f"ChatMessage [{m.role}] {m.text[:60]} | payload keys={sorted((m.payload or {}).keys())}")
    session.close()

    print("\n──────── 回覆 ────────")
    advice = final.get("advice") or {}
    print("reply:", (advice.get("reply") or "")[:400])
    print("items:", json.dumps(advice.get("items", []), ensure_ascii=False))
    print(f"escalate={final.get('escalate')} vision_used={final.get('vision_used')}")

    if cleanup:
        os.unlink(cleanup)


if __name__ == "__main__":
    main()
