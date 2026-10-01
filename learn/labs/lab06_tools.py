"""Lab 06 — Tool call：model 點「要求」用工具，程式點執行

LLM 本身冇記憶、冇資料庫。Agent 嘅做法係俾佢一份**工具清單**，
佢喺結構化輸出度填「我想用邊個工具」，程式見到大就真係去跑，再將結果餵返個 prompt。

⚠️ 關鍵設計：呢個 repo **唔用** provider 嘅 function calling，而係要求 model 喺
   `SkinAnalysis.tool_calls` 呢個字串陣列度填工具名。原因見課程 §02（DeepSeek thinking mode
   唔准強制 tool_choice、同埋要換 provider 都行得）。

跑法：  ./backend/.venv/bin/python learn/labs/lab06_tools.py
"""
from _common import graph_runner, note, seed_conversation, step, temp_db, title, warn

from app.agent.llm import FakeLLM
from app.agent.tools import WHITELIST, run_tool

title("Lab 06 — Tool call 嘅兩個半邊")

step(1, "白名單：agent 可以叫嘅工具就係得呢三個（`app/agent/tools.py`）")
print(f"  WHITELIST = {sorted(WHITELIST)}")
print("  get_skin_profile   : 讀長期記憶（insights，帶 confidence／expiry）")
print("  get_recent_entries : 讀最近幾日結構化紀錄（entry + attributes）")
print("  search_knowledge   : RAG 檢索（lab05）")
note("冇 shell、冇 HTTP、冇 eval —— 唔存在「model 亂叫就會執行危險操作」呢件事。")

step(2, "第一邊：model 要求（analyze node 嘅輸出）")
print("  SkinAnalysis.tool_calls = ['get_skin_profile', 'search_knowledge']")
print("  呢個係**模型嘅決定**；程式唔會自己猜，亦唔會硬編碼。")

step(3, "第二邊：程式執行（tools node）")
sf, _ = temp_db()
cid = seed_conversation(sf)
s = sf()
# 放一條記憶入去，令 get_skin_profile 有嘢回
from app.models import Insight

s.add(Insight(conversation_id=cid, kind="derived", text="T 字位長期偏油", confidence=0.7, direction="problem", tag="oiliness"))
s.commit()
state = {"conversation_id": cid, "user_text": "下巴生瘡", "photo_paths": [], "cloud_analysis": True}
from _common import embedder

emb = embedder()
for name in ["get_skin_profile", "get_recent_entries", "search_knowledge", "hack_the_planet"]:
    out = run_tool(name, state, s, emb)
    rows = len(out["result"]) if isinstance(out.get("result"), list) else "—"
    print(f"  run_tool({name!r:<22}) → rows={rows}  error={out.get('error')}")
s.close()
warn(
    "注意最後一行：唔喺白名單嘅工具名**唔會**執行，只會靜靜回一個 error 記錄（入 trace）。\n"
    "   呢個就係「whitelist 係安全邊界」：model 講咩都冇用，程式先係決定者。"
)

step(4, "完整一次 consult：睇 tools node 嘅 trace")
runner = graph_runner(sf, llm=FakeLLM())
res = runner.invoke(
    {"conversation_id": cid, "user_text": "下巴又有兩粒新瘡", "photo_paths": [], "cloud_analysis": True, "trace": []}
)
for t in res["trace"]:
    if t["node"] == "tools":
        print(f"  requested = {t['detail']['requested']}")
        for r in t["detail"]["ran"]:
            print(f"    {r['tool']:<20} rows={r['rows']} error={r['error']}")
print()
print("  口訣（`scripts/trace_consult.py` 個 docstring 都寫咗）：")
print("    tool_calls 空        → model 冇要求工具 → RAG／記憶完全冇跑")
print("    ran[].rows = 0       → 工具跑咗但冇資料（chunks 空 / 記憶空）")
print("    ran[].error          → tool 爆咗或者名唔喺 whitelist")
print("    advise.tool_rows = 0 → 檢索結果冇入到 prompt（model 憑空答）")
