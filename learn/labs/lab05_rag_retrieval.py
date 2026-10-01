"""Lab 05 — RAG：點樣「搵返相關知識」再放入 prompt

Agent 唔應該靠 model 記憶答護膚問題（會作故事）。呢個 repo 嘅做法：
  1. 事先將文章切 chunk、embed、存落 SQLite（`chunks` table）
  2. 用戶問一句 → embed 佢 → 搵 cosine 最近嘅 N 個 chunk
  3. 將 chunk 原文塞入 prompt，叫 model「只可以用呢啲資料答」

跑法：  ./backend/.venv/bin/python learn/labs/lab05_rag_retrieval.py
"""
from _common import embedder, note, step, temp_db, title, warn

from app.models import Chunk
from app.rag import ingest_text
from app.rag.hybrid import search_hybrid
from app.rag.retrieve import retrieve

KNOWLEDGE = [
    (
        "zh-basics",
        "暗瘡",
        "暗瘡護理重點係唔好擠壓，擠壓會令疤痕更嚴重。"
        "日常用溫和潔面產品，一日唔好洗超過兩次，過度清潔反而會刺激皮膚出更多油。",
    ),
    (
        "zh-basics",
        "防曬",
        "防曬要搽足份量同補搽。紫外線會加深色素沉澱，"
        "所以有色斑或者暗瘡印嘅人特別要用廣譜防曬。",
    ),
    (
        "zh-basics",
        "保濕",
        "保濕唔等於油。皮膚屏障受損會引發補償性出油，"
        "所以清爽 gel 質地嘅保濕產品對油性皮膚一樣重要。",
    ),
]

title("Lab 05 — RAG：由問題到「有引文嘅答案」")

step(1, "準備：臨時 DB ＋ 3 篇小知識（真 app 係 PDF／PMC／DermNet 爬返嚟）")
sf, path = temp_db()
emb = embedder()

s = sf()
total = 0
for source, title_, text in KNOWLEDGE:
    n = ingest_text(s, source=source, text=text, embedder=emb, title=title_)
    total += n
    print(f"  ingest「{title_}」→ {n} 個 chunk")
print(f"  合共 {total} 個 chunk；DB 入面 chunks = {s.query(Chunk).count()}")
s.close()

step(2, "chunk 係咩樣？（切得太大／太細都會影響檢索）")
s = sf()
for c in s.query(Chunk).limit(2):
    print(f"  [{c.id[:8]}] source={c.source} title={c.title} 維度={len(c.embedding or [])}")
    print(f"      text = {(c.text or '')[:60]}…")
s.close()

step(3, "查詢 1：『下巴生瘡，點清潔好？』")
q1 = "下巴生瘡，點清潔好？"
s = sf()
print("  ── 純語意（`retrieve()`，eval 用嘅基準）")
for chunk, score in retrieve(s, q1, emb, top_k=3):
    print(f"     {score:.3f}  [{chunk.title}] {chunk.text[:38]}…")
print("  ── hybrid（`search_hybrid()`，**runtime 真正用嘅**：語意 + 關鍵詞 re-rank）")
for chunk, score in search_hybrid(s, q1, emb, top_k=3):
    print(f"     {score:.3f}  [{chunk.title}] {chunk.text[:38]}…")
s.close()
note("留意兩個名次可能唔同：hybrid 會獎勵「查詢同 chunk 有共同字詞」嘅結果（BOOST）。")

step(4, "查詢 2：用同義詞（唔同字面）")
q2 = "塊面成日泛油光，可以點做？"
s = sf()
print(f"  查詢：{q2}")
for chunk, score in search_hybrid(s, q2, emb, top_k=3):
    print(f"     {score:.3f}  [{chunk.title}] {chunk.text[:38]}…")
s.close()
warn(
    "睇下個分數：0.285／0.074／0.066 —— 三個都低，而且第一同第二名差好遠但其實唔相關。\n"
    "   同義詞（泛油光 vs 出油）hash embedder 撞唔中，排第一只係字面巧合。真 model（lab04 ②）先分得開。\n"
    "   呢個 lab 刻意用 hash embedder，就係想你自己見到：**檢索質素 = embedding 質素**。"
)

step(5, "空語料庫會點？（新安裝嘅 app 就係噉）")
sf2, _ = temp_db()
s = sf2()
print(f"  空 DB 檢索結果 = {retrieve(s, q1, emb, top_k=3)}")
print("  → graph 嘅 tools node 會記低 rows=0（唔會爆），advise 照答但冇引文。")
print("  → 所以 `ingest_corpus.py` 一定要跑過，否則 RAG 等於冇。")
s.close()

step(6, "檢索結果點樣入 prompt？")
print("  `graph.advise` 會將 tool_results 塞入 prompt（見 `prompts.build_advise_prompt`）：")
print("    【工具結果】[{\"tool\": \"search_knowledge\", \"result\": [{text…, score…}]}]")
print("  所以 trace 嘅 `advise.tool_rows` 就係「有幾多條檢索結果真正入到 prompt」——")
print("  tool_rows=0 即係 model 係憑空答（唔應該當成可靠建議）。")
