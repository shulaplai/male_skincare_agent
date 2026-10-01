"""Lab 10 — 自己寫一個 eval（⭐ 課程 §06 嘅配搭實驗）

呢個 lab 唔會改 repo 任何嘢：所有「新檢查」都係喺記憶體入面跑嘅。

你會做四件事：
  1. 睇 `backend/eval/` 由邊幾件砌成
  2. 跑真 eval（臨時 DB ＋ FakeLLM ＋ committed golden corpus）睇真數字
  3. ⭐ 自己加檢查：三條「好」規則 ＋ 一條「太嚴」規則，睇邊條紅
  4. ⭐⭐ 驗證個檢查**識紅** —— 呢一步係全章最重要，唔做就等於冇寫過

跑法：  ./backend/.venv/bin/python learn/labs/lab10_own_eval.py
"""
import json
from pathlib import Path

from _common import BACKEND, note, step, temp_db, title, warn

from app.agent.llm import FakeLLM
from app.rag import DeterministicEmbedder, ingest_file
from app.rag.hybrid import search_hybrid
from eval.agent_eval import run_agent_eval
from eval.rag_recall import evaluate_recall

EVAL_DIR = BACKEND / "eval"
GOLDEN = EVAL_DIR / "golden"

title("Lab 10 — 自己寫一個 eval")

# ── 1. eval/ 由邊幾件砌成 ──────────────────────────────────────────────────
step(1, "eval/ 有咩（指揮 ＋ 三種檢查器）")

PARTS = [
    ("run_eval.py", "指揮：砌臨時 DB、順序跑三類檢查、寫報告、定 exit code"),
    ("agent_eval.py", "檢查器 ①：agent 情境（跑真 graph，驗 escalate／tool rows／安全）"),
    ("rag_recall.py", "檢查器 ②：檢索質素（recall@k ＋ MRR）"),
    ("safety.py", "檢查器 ③：確定性安全（永遠跑，唔要 LLM）"),
    ("judge.py", "參考分：LLM-as-judge 1–5 分（有真 key 先跑）—— **唔係 gate**"),
    ("scenarios.json", "4 個 agent 情境"),
    ("rag_scenarios.json", "5 個檢索查詢"),
    ("golden/", "committed 語料（要入 git，所以要細）"),
]
for name, what in PARTS:
    print(f"  {name:<20} {what}")

print()
print("  ⭐ 分界線：gate 一定係 deterministic（前四件）。judge.py 係**參考分**，")
print("     因為 LLM 同一個輸入唔保證同一個輸出 —— 用佢做 gate 就會 flaky。")

# ── 2. 臨時 DB ＋ golden corpus ────────────────────────────────────────────
step(2, "臨時 DB ＋ ingest golden corpus（唔會掂 backend/data/）")

sf, db_path = temp_db()
print(f"  temp DB: {db_path}")

emb = DeterministicEmbedder()
s = sf()
chunks = 0
files = sorted(GOLDEN.glob("*.txt"))
for p in files:
    n = ingest_file(s, p, emb)
    chunks += n
    print(f"  ingest {p.name:<34} → {n} chunk(s)")
s.close()
print(f"  總共 {chunks} 個 chunk（真 app 嘅 data/corpus 大好多 —— eval 要細先可以每次跑）")

# ── 3. RAG recall：語意 vs hybrid ─────────────────────────────────────────
step(3, "檢查器 ②：檢索 —— 語意 baseline vs runtime 嘅 hybrid")

rag_scen = json.loads((EVAL_DIR / "rag_scenarios.json").read_text())
s = sf()
sem = evaluate_recall(s, rag_scen, emb)
hyb = evaluate_recall(s, rag_scen, emb, retriever=search_hybrid)
s.close()

print(f"  語意 baseline : recall={sem['recall'] * 100:.0f}%  MRR={sem['mrr']:.2f}")
print(f"  hybrid（runtime）: recall={hyb['recall'] * 100:.0f}%  MRR={hyb['mrr']:.2f}")
print()
print(f"  {'query':<12}{'語意 rank':>10}{'hybrid rank':>13}")
for a, b in zip(sem["results"], hyb["results"]):
    print(f"  {a['id']:<12}{str(a['rank']):>10}{str(b['rank']):>13}")

print()
print("  ⭐ 留意 `oily`：語意排第 2，hybrid 排第 1 → MRR 由 0.90 升到 1.00。")
print("     呢個就係「為咩要 hybrid」嘅**可量度**理由（唔係『我覺得好啲』）。")
print("  ⚠️ 但只有 4 個 chunk：recall 100% 唔代表真 corpus 都 100%。")

# ── 4. 跑 agent scenario ──────────────────────────────────────────────────
step(4, "檢查器 ①：agent 情境（4 個 scenario 行真 graph）")

scen = json.loads((EVAL_DIR / "scenarios.json").read_text())


def make_conversation() -> str:
    """⭐ 每個 scenario 一定要一個**新** conversation。

    共用嘅話，「已有記憶」嗰條路會變成靠洩漏（上一個 scenario 寫落嘅 Entry），
    而且記憶 confidence 會無故由 0.60 升到 0.70。`run_agent_eval` 會逐個 call 呢個函數。
    """
    from app import crud

    s = sf()
    try:
        return crud.create_conversation(s, "面部皮膚", "🧔").id
    finally:
        s.close()


results = run_agent_eval(scen, sf, emb, FakeLLM(), make_conversation)
print(f"  {'id':<16}{'passed':<8}{'escalate':<10}{'first_checkin':<15}tools")
for r in results:
    tools = " · ".join(f"{k}={v}" for k, v in r["tools"].items())
    print(
        f"  {r['id']:<16}{str(r['passed']):<8}{str(r['escalate']):<10}"
        f"{str(r['first_checkin']):<15}{tools}"
    )

print()
print("  ⭐ `returning_user` 用咗 seed_days=3（播歷史），所以 first_checkin=False；")
print("     其餘三個都 True → 證明 scenario 之間**真嘅隔離**。")

# ── 5. ⭐ 自己加檢查 ──────────────────────────────────────────────────────
step(5, "⭐ 自己加檢查：三條好規則 ＋ 一條太嚴嘅規則")

CLIP_WORDS = ("幾張相", "抽格", "格數", "frames")

RULES = [
    ("R1 每條 item ≤ 40 字", lambda r: all(len(i) <= 40 for i in r["advice_items"])),
    ("R2 唔可以提「幾張相／抽格」", lambda r: not any(w in _all_text(r) for w in CLIP_WORDS)),
    ("R3 first_checkin 要對得上 seed", lambda r: r["first_checkin"] == (r["seed_days"] == 0)),
    ("R4（太嚴）一定要 ≥ 3 條 item", lambda r: len(r["advice_items"]) >= 3),
]


def _all_text(r) -> str:
    return " ".join(r["advice_items"]) + " " + str(r.get("advice") or "")


def _dw(s) -> int:
    """顯示寬度：中日韓全形字計 2 格。

    ⚠️ `f"{s:<32}"` 係計**字數**唔係**格數** —— 中英夾雜嘅表格一定會歪。
    （呢個 lab 第一版就係咁歪咗，所以先要有呢個 helper。）
    """
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(s))


def _pad(s, width: int) -> str:
    return str(s) + " " * max(0, width - _dw(s))


def run_rules(rs, rules):
    """回傳 {rule_name: [bool, ...]} —— 同 run_eval 一樣，逐 scenario 評分。"""
    return {name: [fn(r) for r in rs] for name, fn in rules}


RULE_COL = 36
scores = run_rules(results, RULES)
print("  " + _pad("rule", RULE_COL) + "".join(f"{r['id']:>16}" for r in results) + "   結論")
print("  " + "─" * 78)
for name in scores:
    row = scores[name]
    cells = "".join(f"{'PASS' if v else 'FAIL':>16}" for v in row)
    verdict = "全部綠" if all(row) else f"{row.count(False)}/{len(row)} 紅"
    print("  " + _pad(name, RULE_COL) + cells + "   " + verdict)

print()
print("  R1–R3 綠：佢哋係『退步就一定要紅』嘅真保證。")
print("     R3 特別有意思 —— 佢守嘅係『scenario 隔離』，即係 eval 自己嘅正確性。")
print()
print("  R4 紅（4/4 FAIL）：FakeLLM 每次只出 2 條 item，所以呢條規則喺 --fake 之下")
print("     永遠紅。表面睇係「產品唔達標」，實際係「我要求得太具體」。")

# ── 6. ⭐⭐ 驗證個檢查識紅 ────────────────────────────────────────────────
step(6, "⭐⭐ 最重要嘅一步：反轉條件，確認個檢查**識紅**")

reversed_rules = [
    ("R3 反轉（故意寫錯）", lambda r: r["first_checkin"] != (r["seed_days"] == 0)),
    ("R1 反轉（故意寫錯）", lambda r: not all(len(i) <= 40 for i in r["advice_items"])),
]
rev = run_rules(results, reversed_rules)
for name in rev:
    row = rev[name]
    print(f"  {name:<28} 紅咗 {row.count(False)}/{len(row)} → " + ("✅ 識紅" if not all(row) else "❌ 唔識紅"))

print()
print("  ⭐ 如果一個檢查反轉咗都仲係綠，佢就係**裝飾** —— 唔係保證。")
print("     做完新檢查，一定要行呢一步先好 commit。")
print()
print("  呢個 repo 用同樣手法驗過：hybrid 接線（test_hybrid）、")
print("  observes_skin 閘門（lab08）、medical term 掃 reply（lab07）。")

# ── 7. FakeLLM 常數 ──────────────────────────────────────────────────────
step(7, "⚠️ 為咩 --fake 綠燈唔等於 model 冇問題")

print("  4 個 scenario 嘅 items（FakeLLM 嘅輸出）：")
for i, it in enumerate(results[0]["advice_items"]):
    print(f"    item{i}: {it}  ({len(it)} 字)")
same = len({tuple(r["advice_items"]) for r in results}) == 1
print()
print(f"  四個 scenario 嘅 items 係唔係完全一樣？ → {same}")
print()
print("  ⭐ 所以任何『文筆／內容』檢查（例如「答案要提到防曬」）喺 --fake 之下")
print("     都係喺量 FakeLLM 嗰句常數，唔係量 model。")
print()
print("  --fake 驗到嘅：管道（5 站接得啱、閘門有冇開、資料有冇寫入）")
print("  --fake 驗唔到嘅：文筆、tool 選擇、vision 行為 → 要 --real 或 judge.py")

note(
    "帶走：**unit test 問「有冇爆」，eval 問「有冇變差」**。\n"
    "    寫 eval 嘅工夫唔在於寫檢查，而在於**確認個檢查識紅** ——\n"
    "    一個永遠綠嘅檢查比冇檢查更危險，因為佢會令你放心。\n"
    "    課程 §06 有完整版（包括兩個真實教訓：gate 指錯路徑、eval 同 guardrail 同一個盲點）。"
)

warn(
    "呢個 lab 完全冇改 repo、冇掂真 data、冇 call 真 model。\n"
    "    想睇真報告：cat backend/eval/out/report.md（由 `python -m eval.run_eval --fake` 產生）"
)
