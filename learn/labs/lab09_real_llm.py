"""Lab 09 — 用真 LLM 跑同一條路（可選，會用真 API key）

⚠️ 呢個 lab 會**真嘅**打去 DeepSeek（讀 `backend/.env` 嘅 key）：
   · 每次跑大約用幾個 request 嘅額度
   · 你打嘅文字會離開你部機（相片分析仲會送圖）
   · 所以預設**唔會**跑，要你自己加 `--real`

跑法：  ./backend/.venv/bin/python learn/labs/lab09_real_llm.py --real
        （唔加 --real 就只會示範會送咩出去，唔會真 call）
"""
import sys

from _common import graph_runner, note, seed_conversation, step, temp_db, title, trace_table, warn

from app.agent.llm import FakeLLM, get_llm
from app.config import settings

REAL = "--real" in sys.argv

title("Lab 09 — FakeLLM vs 真 LLM")

step(1, "邊個 adapter 會被揀？（`app/agent/llm.py: get_llm()`）")
print(f"  provider           = {settings.llm_provider}")
print(f"  text model         = {settings.deepseek_text_model}")
print(f"  vision model       = {settings.deepseek_vision_model}")
print(f"  有冇 key           = {bool(settings.deepseek_api_key)}")
print(f"  get_llm('text') 回 = {type(get_llm('text')).__name__}")
note(
    "有 key → 真 adapter；冇 key → FakeLLM（罐頭輸出，整條 pipeline 照跑得通）。\n"
    "   呢個設計令 CI／demo／教學都唔需要密鑰，但**唔代表**測試驗證咗 model 行為。"
)

step(2, "FakeLLM 係咩？（`app/agent/llm.py: class FakeLLM`）")
out = FakeLLM().structured("system", "user", __import__("app.agent.schemas", fromlist=["SkinAnalysis"]).SkinAnalysis)
print(f"  回一個固定嘅 SkinAnalysis：observes_skin={out.observes_skin}, attributes={len(out.attributes)}")
warn(
    "所以 pytest + eval --fake 全綠 **唔等於** model 行為正確。真 model 要另外驗（`--real`）。\n"
    "   歷史上撞過：FakeLLM 硬編碼 tool 名，而真 model 完全唔識叫 tool → 上 production 即爆。"
)

step(3, "真 call 會送咩出去（就算唔跑都值得知）")
from app.agent.prompts import ANALYZE_SYSTEM, build_analyze_prompt

p = build_analyze_prompt("下巴爆咗兩粒瘡", has_photo=False)
print(f"  system prompt {len(ANALYZE_SYSTEM)} 字 ＋ user prompt {len(p)} 字 → {settings.llm_provider}")
print("  有相嘅話：圖片會 base64 塞入 messages（所以 consent 係 code gate，唔係 UI 好唔好意思）")

if not REAL:
    print("\n（冇加 --real，所以到此為止。想真跑：加 --real）")
    raise SystemExit(0)

step(4, "真跑一次（同一條 5-node 路，只係 adapter 唔同）")
sf, _ = temp_db()
cid = seed_conversation(sf)
llm = get_llm("text")
runner = graph_runner(sf, llm=llm, vision_llm=get_llm("vision"))
res = runner.invoke(
    {
        "conversation_id": cid,
        "user_text": "下巴爆咗兩粒瘡，T 字位好油，應該點護理？",
        "photo_paths": [],
        "cloud_analysis": True,
        "trace": [],
    }
)
trace_table(res)
adv = res.get("advice") or {}
print("\n  真 model 回覆：")
for line in str(adv.get("reply", ""))[:400].split("。"):
    if line.strip():
        print(f"    {line.strip()}。")
print(f"  items = {adv.get('items')}")
print(f"  detected_events = {adv.get('detected_events')}")
note(
    "對比 lab03（FakeLLM）：trace 結構一模一樣，但 reply 係真嘅廣東話護膚建議。\n"
    "   呢個就係 adapter pattern 嘅威力：**換 model 唔使改 pipeline**。"
)
