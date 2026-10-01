"""實驗共用工具。

⭐ 呢個檔唔屬於 app —— 係教學用嘅「枱面」：幫你建立一個**臨時 DB**、印靚啲 banner、
同確保實驗永遠唔會掂到你真嘅 `backend/data/skincoach.db`。

跑實驗之前，先明白三件事（課程 §05 會詳細講）：
  1. 呢啲 script 全部用 `sys.path.insert(...)` 直接 import `backend/app/*`，
     所以你喺任何目錄都可以跑（唔使先 cd 入 backend）。
  2. 每個實驗都用**自己嗰個臨時 SQLite**（`tempfile`）＋ `FakeLLM`：
     零 API 費用、零真 data 風險。想用真 LLM 就睇 `lab09_real_llm.py`。
  3. 實驗印嘅嘢係「真輸出」—— 課程文件裏面嘅預期輸出就係噉樣 capture 出嚟。
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

# ── 1. 令 `import app.*` 行得通（唔理你由邊個目錄跑）────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# ── 2. 靜音：app 內部嘅 warning 會蓋住教學輸出（想睇就 VERBOSE=1）──────────
if not os.environ.get("VERBOSE"):
    logging.basicConfig(level=logging.ERROR)
    for name in ("app", "app.agent", "app.rag", "httpx", "sentence_transformers", "fastembed"):
        logging.getLogger(name).setLevel(logging.ERROR)


WIDTH = 74


def title(text: str) -> None:
    print("\n" + "═" * WIDTH)
    print(f"  {text}")
    print("═" * WIDTH)


def step(n: int | str, text: str) -> None:
    print(f"\n── 步驟 {n}：{text} " + "─" * max(0, WIDTH - 12 - len(str(n)) - len(text)))


def note(text: str) -> None:
    print(f"\n📌 {text}")


def warn(text: str) -> None:
    print(f"\n⚠️  {text}")


def show(label: str, value) -> None:
    print(f"{label}: {value}")


def temp_db():
    """一個乾淨嘅臨時 SQLite sessionmaker（同 app 用同一個 schema）。

    ⚠️ 每次 call 都係**新** DB —— 實驗之間唔會互相污染，亦唔會掂你真 data。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base

    tmp = tempfile.NamedTemporaryFile(prefix="learn_", suffix=".db", delete=False)
    engine = create_engine(f"sqlite:///{tmp.name}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine), tmp.name


def seed_conversation(sf, body_part: str = "面部皮膚") -> str:
    """開一個 conversation（因為 app 所有資料都掛喺 conversation 度）。"""
    from app.models import Conversation, User

    s = sf()
    user = User(name="學習者")
    s.add(user)
    s.flush()
    conv = Conversation(user_id=user.id, body_part=body_part)
    s.add(conv)
    s.commit()
    cid = conv.id
    s.close()
    return cid


def embedder():
    """教學用 embedder：字元 bigram hashing，128 維，冇下載、冇依賴、100% 確定性。

    （真 app 用 `FastembedEmbedder`（MiniLM、384 維）—— 見 lab04／lab05。）
    """
    from app.rag import DeterministicEmbedder

    return DeterministicEmbedder()


def graph_runner(sf, *, llm, vision_llm=None, emb=None):
    """建立一個跑得嘅 5-node graph（同 production 同一個 `build_graph`）。"""
    from app.agent.graph import build_graph

    return build_graph(
        llm=llm,
        vision_llm=vision_llm or llm,
        session_factory=sf,
        embedder=emb or embedder(),
    )


def invoke(runner, cid: str, text: str, *, photo_paths=None, cloud_analysis=True):
    """跑一次完整 consult（同 HTTP POST /api/consult 走同一條路）。"""
    return runner.invoke(
        {
            "conversation_id": cid,
            "user_text": text,
            "photo_paths": photo_paths or [],
            "cloud_analysis": cloud_analysis,
            "trace": [],
        }
    )


def trace_table(result: dict) -> None:
    """印出 `state['trace']`：逐個 node 做咗咩、幾多毫秒。"""
    rows = result.get("trace") or []
    print(f"{'node':<11}{'ms':>7}  摘要")
    print("─" * WIDTH)
    for t in rows:
        summary = {k: v for k, v in t.items() if k not in ("node", "ms", "at")}
        print(f"{t.get('node', '?'):<11}{t.get('ms', 0):>7.1f}  {summary}")
