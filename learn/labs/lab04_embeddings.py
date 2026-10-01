"""Lab 04 — Embedding：把文字變成 vector，同「相似」到底係咩意思

⭐ 呢個 lab 有一個**驚喜**：同一組句子，用「假 embedder」同「真 model」計出嚟嘅相似度
   係**反轉**嘅。呢個唔係 bug，係一堂重要嘅課：唔係所有「vector」都識語意。

跑法：  ./backend/.venv/bin/python learn/labs/lab04_embeddings.py
"""
import os

from _common import BACKEND, note, step, title, warn

from app.rag.embeddings import DeterministicEmbedder

TEXTS = [
    "下巴爆咗兩粒暗瘡，T 字位好油",
    "額頭生瘡同出油，唔知點算",
    "防曬要搽足，紫外線會加深色斑",
    "今晚食咗麻辣火鍋",
]


def cosine(a, b):
    """兩個 vector 嘅 cosine similarity：1 = 方向一樣、0 = 無關。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


def matrix(vecs, label=""):
    print(f"\n  {label}")
    print(f"{'':<26}" + "".join(f"{t[:8]:>10}" for t in TEXTS))
    for i, t in enumerate(TEXTS):
        print(f"{t[:24]:<26}" + "".join(f"{cosine(vecs[i], vecs[j]):>10.3f}" for j in range(len(TEXTS))))


title("Lab 04 — Embedding 同 cosine similarity")

step(1, "Embedding 係咩？")
print("  文字 → [0.02, -0.11, 0.30, …]（一串浮點數，叫做 vector）")
print("  意思相近 → vector 方向相近；大細（長度）唔重要，所以用 cosine 比**方向**。")
print("  維度（vector 幾長）由 model 決定 —— 呢個係「型別」嘅一部分。")

step(2, "呢個 codebase 有兩種 embedder（`app/rag/embeddings.py`）")
print("  FastembedEmbedder     : 真 model（multilingual-MiniLM，384 維，第一次要下載）")
print("  DeterministicEmbedder : 字元 bigram hashing（128 維，冇 model、確定性）")

step(3, "先睇 deterministic 版（教學／test 用，零成本）")
e = DeterministicEmbedder()
matrix([e.embed(t) for t in TEXTS], "① DeterministicEmbedder（128 維，hash）")

step(4, "⚠️ 慢住 —— 呢個結果係「字面重疊」，唔係「語意」")
print("  「下巴爆咗兩粒暗瘡」vs「額頭生瘡同出油」 = 0.067（應該好高，但好低）")
print("  「下巴爆咗兩粒暗瘡」vs「防曬要搽足」     = 0.286（應該中等，但最高）")
note(
    "hash embedder 只係將每個字元 bigram 掟入 hash 桶，所以佢量到嘅係「有幾多字面相同」，\n"
    "   唔係「意思有幾近」。中文同義詞（瘡 vs 暗瘡、出油 vs 油）對佢嚟講完全唔同。"
)

step(5, "換真 model 睇下（multilingual-MiniLM，384 維）")
real = None
os.environ.setdefault("FASTEMBED_CACHE_PATH", str(BACKEND / "data" / ".fastembed-cache"))
os.environ.setdefault("SKINCOACH_EMBEDDER_CACHE_DIR", str(BACKEND / "data" / ".fastembed-cache"))
os.environ.setdefault("HF_HOME", str(BACKEND / "data" / ".hf-cache"))
try:
    from app.rag.embeddings import FastembedEmbedder

    real = FastembedEmbedder()
    rv = [real.embed(t) for t in TEXTS]
    print(f"  真 model 維度 = {len(rv[0])}")
    matrix(rv, "② FastembedEmbedder（384 維，真 model）")
    print("\n  同上面 ① 對比：")
    print("   暗瘡 ↔ 出油      : ① 0.067   →   ② 0.738   ✅ 語意正確")
    print("   暗瘡 ↔ 防曬      : ① 0.286   →   ② 0.220")
    print("   火鍋 ↔ 防曬      : ① 0.105   →   ② 0.033   ✅ 最唔相關")
    note("真 model 識「暗瘡同出油係同一件事」；hash 版唔識。**所以 production 一定要用真 model。**")
except Exception as err:  # 冇 cache／離線／冇寫入權
    warn(f"跳過真 model（{type(err).__name__}: {str(err)[:80]}）—— 呢個唔影響課程其他部分。")

step(6, "⚠️ 兩個維度唔可以混（真實 bug 級陷阱）")
note(
    "如果你嘅 DB 入面係 384 維 chunk，但 runtime 用咗 128 維 embedder（例如 cache 寫唔到 →\n"
    "   靜靜 fallback），`_cosine` 用 `zip()` 只會比前 128 個數 → **分數完全冇意義但唔會報錯**。\n"
    "   呢個就係 `AGENTS.md` 點解要寫死 `FASTEMBED_CACHE_PATH`／`SKINCOACH_EMBEDDER_CACHE_DIR`。\n"
    "   `vectorstore.add_chunks` 會 raise、`search` 會跳過維度唔夾嘅 chunk 並 log warning。"
)

step(7, "順帶一提：model 版本會影響結果")
print("  跑呢個 lab 你可能會見到 fastembed 警告「model 而家改用 mean pooling」。")
print("  現實世界嘅 lesson：embedding model 一升級，你就應該**重新 index** 成個語料庫。")
