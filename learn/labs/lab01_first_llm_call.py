"""Lab 01 — 「LLM call」喺呢個 codebase 到底係咩樣？

跑法：  cd backend && ./.venv/bin/python ../learn/labs/lab01_first_llm_call.py
        （或者由 repo root： ./backend/.venv/bin/python learn/labs/lab01_first_llm_call.py）

呢個 lab 想拆穿一件事：**LLM 唔係魔法，喺 code 入面佢就係一個 interface**。
你喺 SkinCoach 見到嘅所有「AI」，最後都收窄到呢一個 method：

    llm.structured(system_prompt, user_prompt, pydantic_schema) -> pydantic_object

冇 hidden state、冇背景魔法 —— 你送一個字串入去，佢回一個**符合 schema 嘅物件**。
"""
from _common import note, show, step, title

from app.agent.llm import FakeLLM, get_llm
from app.agent.prompts import ANALYZE_SYSTEM, build_analyze_prompt
from app.agent.schemas import SkinAnalysis

title("Lab 01 — 一個 LLM call 由頭到尾")

step(1, "呢個 interface 有咩 method？（`app/agent/llm.py`）")
for name in ("structured", "structured_vision"):
    print(f"  - {name}(...)：{'文字 → 結構化輸出' if name == 'structured' else '文字＋圖片 → 結構化輸出'}")
note("兩個 method 都收一個 Pydantic schema，回一個**已經驗證過**嘅物件。")

step(2, "真正送去 model 嘅嘢：system prompt ＋ user prompt")
print(f"ANALYZE_SYSTEM（{len(ANALYZE_SYSTEM)} 字）頭 120 字：")
print("  " + ANALYZE_SYSTEM[:120].replace("\n", " ") + "…")
prompt = build_analyze_prompt("下巴爆咗兩粒瘡，T 字位好油", has_photo=False)
print(f"\nbuild_analyze_prompt(...)（{len(prompt)} 字）：")
for line in prompt.splitlines():
    print("  " + line)

step(3, "誰做「結構化」？Pydantic schema（`app/agent/schemas.py`）")
show("SkinAnalysis 欄位", list(SkinAnalysis.model_fields.keys()))
print("  attributes 裏面每一項要 {key, severity, note}；key 只可以係固定六個之一。")
note("呢個 schema 就係「型別合約」：model 唔可以自由發揮，出錯會被 Pydantic 擋。")

step(4, "實際 call（用 FakeLLM：唔會上網、唔會收錢）")
show("llm 係咩", type(FakeLLM()).__name__)
result = FakeLLM().structured(ANALYZE_SYSTEM, prompt, SkinAnalysis)
print(f"  回傳型別: {type(result).__name__}")
print(f"  observes_skin: {result.observes_skin}")
print(f"  attributes: {[(a.key, a.severity) for a in result.attributes]}")

step(5, "Production 會用邊個 adapter？")
real = get_llm("text")
show("get_llm('text') 回", type(real).__name__)
note(
    "呢個 deployment 嘅 backend/.env 有真 key，所以 get_llm() 回真 adapter（OpenAICompatLLM）。\n"
    "   測試同實驗一律**自己傳** FakeLLM 入去，否則每次跑 test 都會燒 API 額度。\n"
    "   課程 §02 會解釋 Adapter pattern 同「點解要有一個假嘅」。"
)
