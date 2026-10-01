"""Lab 02 — 為咩要「結構化輸出」？Pydantic schema 擋咩？

LLM 天生只識出文字。要佢融入一段程式，就要一條**合約**：
「你唔係寫文章，你要填呢個 JSON 形狀」。呢個 lab 示範合約點樣擋住垃圾。
"""
import json

from _common import note, show, step, title, warn

from app.agent.prompts import ANALYZE_SYSTEM, build_analyze_prompt
from app.agent.schemas import Advice, SkinAnalysis

title("Lab 02 — 合約：Pydantic schema")

step(1, "三個關鍵 schema")
print("  SkinAnalysis : 睇相／睇字之後嘅結構化分析（observes_skin、attributes、tool_calls…）")
print("  Advice       : 教練回覆（reply、items、detected_events…）")
print("  DetectedEvent: 自報事件（diet / product_start / product_stop）")

step(2, "合約點寫（`app/agent/schemas.py` 節錄）")
print("  attributes: 六個固定 key（acne/oiliness/redness/dryness/pores/texture）× severity 0–3")
print(f"  SkinAnalysis 必要欄位: {SkinAnalysis.model_fields['observes_skin'].annotation}")

step(3, "如果 model 亂出（唔跟合約）會點？")
bad = {"summary": "睇落唔錯", "attributes": [{"key": "靚仔度", "severity": 5}]}
print("  送呢個入去:", json.dumps(bad, ensure_ascii=False))
try:
    SkinAnalysis(**bad)
except Exception as e:
    warn(f"被擋住 → {type(e).__name__}")
    for line in str(e).splitlines()[:6]:
        print("    " + line)
note(
    "重點：錯嘅 key、超出 0–3 嘅 severity 都入唔到系統。\n"
    "   所以 guardrail / timeline / 記憶呢啲下游 code 可以假設「數值一定合理」——\n"
    "   呢個就係 AGENTS.md 約定 #3「所有 LLM 輸出強制 Pydantic」嘅原因。"
)

step(4, "合約同時係「提示」：schema 會變成人交俾 model 嘅說明")
for k, f in list(SkinAnalysis.model_fields.items())[:5]:
    desc = (f.description or "")[:46]
    print(f"  {k:<15} {str(f.annotation)[:24]:<26} {desc}")
note("你寫嘅 description 就係叫 model 點填。改 prompt 之前，先睇 schema 寫咗咩。")

step(5, "順便示範：`observes_skin` 呢個閘")
print("  observes_skin=False 代表「今次唔係皮膚紀錄」（例如問產品）")
print("  persist node 見到 False（而且冇 vision）就**唔會**寫 Entry —— 課程 §04／lab08 會實測。")

step(6, "Advice 有幾個欄位")
show("Advice", list(Advice.model_fields.keys()))
print("  reply = 用戶睇到嘅正文；items = 卡片 bullet；detected_events = 等用戶確認嘅自報事件")
