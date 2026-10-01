"""Lab 08 — Persist 嘅閘門：為咩問一句產品問題唔會變成「一日皮膚數據」

呢個 lab 示範「deterministic core」最容易撞爛嘅地方：**寫入閘門**。

背景（真曾發生）：以前每一條訊息都當「打卡」，而 ANALYZE_SYSTEM 話「未提及就畀 0」，
所以問「呢支精華得唔得？」會寫入一組**全 0** 嘅當日讀數，覆蓋你真實嘅紀錄。
而因為「一日只准一個 agent event」，假嘅「改善」仲會被永久凍結。

而家嘅閘：`persist` 只喺 `analysis.observes_skin == True` **或者** vision 真係睇過相嗰陣才寫 Entry。

跑法：  ./backend/.venv/bin/python learn/labs/lab08_persist_gate.py
"""
from _common import graph_runner, note, seed_conversation, step, temp_db, title, trace_table

from app.agent.llm import FakeLLM
from app.models import ChatMessage, Entry, Insight

title("Lab 08 — 寫入閘門（Entry gate）")


def run(sf, cid, text, observes: bool):
    """用一個「照你話事」嘅 stub LLM：直接控制 observes_skin，唔靠估關鍵詞。"""

    class Stub(FakeLLM):
        def structured(self, system, user, schema):
            out = super().structured(system, user, schema)
            if hasattr(out, "observes_skin"):
                out.observes_skin = observes
            return out

    return graph_runner(sf, llm=Stub()).invoke(
        {"conversation_id": cid, "user_text": text, "photo_paths": [], "cloud_analysis": True, "trace": []}
    )


sf, _ = temp_db()
cid = seed_conversation(sf)

step(1, "情境 A：問產品（model 判定 observes_skin = False）")
res = run(sf, cid, "呢支煙酰胺精華得唔得？", observes=False)
trace_table(res)
s = sf()
print(f"  Entry 數量 = {s.query(Entry).count()}   ← 冇寫入 ✅")
print(f"  ChatMessage 數量 = {s.query(ChatMessage).count()}   ← 對話本身照存（reload 要睇得到）")
s.close()
note("呢個就係 Entry（data truth）同 ChatMessage（display truth）分家嘅意思 —— 約定 #5。")

step(2, "情境 B：真打卡（model 判定 observes_skin = True）")
res2 = run(sf, cid, "今日下巴爆咗兩粒瘡，T 字位好油", observes=True)
trace_table(res2)
s = sf()
entry = s.query(Entry).order_by(Entry.date.desc()).first()
print(f"  Entry 數量 = {s.query(Entry).count()}   ← 寫咗 ✅")
if entry:
    print(f"  最新 Entry：date={entry.date} attributes={[(a['key'], a['severity']) for a in (entry.attributes or [])]}")
print(f"  Insights = {s.query(Insight).count()} 條（記憶係由紀錄衍生出嚟）")
s.close()

step(3, "如果冇呢個閘會發生咩事？")
print("  1. 問產品 → 全 0 讀數蓋掉當日真紀錄")
print("  2. 全 0 被當「改善」（severity 由 3 變 0）")
print("  3. 「一日只准一個 agent event」→ 假改善永久凍結，真打卡都改唔返")
print("  4. 下游（記憶 reconcile、相關性偵測、商品評估）全部食錯數")
note(
    "所以閘門係用**結構化欄位**（observes_skin）而唔係關鍵詞猜測。\n"
    "   model 負責判斷「呢句係唔係皮膚觀察」，程式負責「判斷結果要唔要寫入」——各司其職。"
)

step(4, "同一個設計哲學喺其他位出現")
print("  · 貼成份表 → graph.tools 偵測到就跑 evaluate_product，但**唔寫 Entry**")
print("  · 自報事件（食咗辣）→ 唔會自動寫入，要用戶撳「✅ 記低」（consent by confirmation）")
print("  · 記憶 reconcile 用 tag + direction（唔係比 text）→ 唔會因為改咗措辭而當新記憶")
