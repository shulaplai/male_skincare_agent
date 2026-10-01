"""Lab 03 — Agent 嘅「思考過程」：5 個 node 逐步行

⭐ 呢個係成個課程嘅核心 lab。跑完你會見到一次 consult 由頭到尾經過五站，
   每站做咩、寫咗咩入 state、花咗幾多毫秒。

跑法：  ./backend/.venv/bin/python learn/labs/lab03_agent_loop.py
"""
import json

from _common import graph_runner, note, seed_conversation, step, temp_db, title, trace_table

from app.agent.llm import FakeLLM

title("Lab 03 — 一次 consult 嘅 5 個 node")

step(1, "Graph 喺邊度砌？（`app/agent/graph.py` 尾段）")
print("""  g = StateGraph(AgentState)
  g.add_node("analyze", analyze)     # 睇相／睇字 → 結構化分析
  g.add_node("tools", tools)         # 跑 model 要求嘅工具（記憶／RAG）
  g.add_node("advise", advise)       # 寫回覆（會帶埋工具結果）
  g.add_node("guardrail", guardrail) # deterministic 安全閘
  g.add_node("persist", persist)     # 寫 DB：Entry／記憶／timeline／chat
  g.add_edge(START, "analyze") → tools → advise → guardrail → persist → END""")

step(2, "準備：臨時 DB ＋ 一個 conversation")
sf, path = temp_db()
cid = seed_conversation(sf)
print(f"  temp DB: {path}")
print(f"  conversation_id: {cid}")

step(3, "跑！留意每一站嘅 delta（`graph.stream()` 會逐 node 吐 state 更新）")
runner = graph_runner(sf, llm=FakeLLM())
state = {
    "conversation_id": cid,
    "user_text": "今日下巴爆咗兩粒瘡，T 字位好油，我應該點做？",
    "photo_paths": [],
    "cloud_analysis": True,
    "trace": [],
}
final: dict = {"trace": []}
for chunk in runner.stream(state):
    for node, delta in chunk.items():
        keys = [k for k in delta if k != "trace"]
        print(f"  → {node:<10} 更新咗 state 嘅: {keys or '（冇）'}")
        if node == "analyze":
            tr = (delta.get("trace") or [{}])[0]
            d = tr.get("detail") or {}
            print(f"      analyze trace: { {k: v for k, v in tr.items() if k not in ('node', 'ms')} }")
            a = delta.get("analysis") or {}
            print(f"      analysis.observes_skin = {a.get('observes_skin')}")
            print(f"      analysis.tool_calls    = {a.get('tool_calls')}")
            # ⚠️ `vision_reason` 淨係喺 trace detail 度，**唔喺 state delta 度**。
            #    直接寫 `delta.get("vision_reason")` 會永遠印 None —— 呢個係真陷阱：
            #    「node 冇回嘅欄位，state 就冇」，唔好當 trace 嘅內容係 state。
            print(f"      vision_used = {delta.get('vision_used')} / vision_reason = {d.get('vision_reason')}")
        if node == "tools":
            d = ((delta.get("trace") or [{}])[0].get("detail") or {})
            print(f"      requested（model 要求）: {d.get('requested')}")
            print(f"      跑咗: {[(r.get('tool'), r.get('rows')) for r in (d.get('ran') or [])]}")
            print(f"      first_checkin = {d.get('first_checkin')} / recent_messages = {d.get('recent_messages')}")
        if node == "advise":
            d = ((delta.get("trace") or [{}])[0].get("detail") or {})
            print(f"      prompt_chars = {d.get('prompt_chars')} / tool_rows = {d.get('tool_rows')}")
            adv = delta.get("advice") or {}
            print(f"      reply（頭 60 字）: {str(adv.get('reply', ''))[:60]}…")
            print(f"      items: {len(adv.get('items') or [])} 條")
        if node == "guardrail":
            d = ((delta.get("trace") or [{}])[0].get("detail") or {})
            print(f"      escalate = {delta.get('escalate')} / disclaimer_added = {d.get('disclaimer_added')}")
        if node == "persist":
            d = ((delta.get("trace") or [{}])[0].get("detail") or {})
            print(f"      entry_written = {d.get('entry_written')} / insights_created = {d.get('insights_created')}")
            print(f"      attributes 寫咗 = {d.get('attributes')} / photos_added = {d.get('photos_added')}")
        # ⚠️ `trace` 用 `Annotated[list, operator.add]` reducer：喺 `stream()` 之下
        #    每個 delta 只係「呢一站加咗嘅 trace」，所以示範要自己 append（唔可以直接 update）。
        final.setdefault("trace", []).extend(delta.get("trace") or [])
        final.update({k: v for k, v in delta.items() if k != "trace"})

step(4, "成個 trace 一覽（呢個就係 `state['trace']`，`/api/consult` 都會回）")
trace_table({"trace": final.get("trace")})

step(5, "最終 state 有咩 key？（呢個就係「agent 嘅記憶體」）")
print("  " + ", ".join(sorted(final.keys())))

step(6, "寫咗入 DB 咩？")
from app.models import ChatMessage, Entry, Insight, TimelineEvent

s = sf()
counts = {
    "entries": s.query(Entry).count(),
    "insights": s.query(Insight).count(),
    "timeline": s.query(TimelineEvent).count(),
    "chat_messages": s.query(ChatMessage).count(),
}
s.close()
print(f"  {json.dumps(counts, ensure_ascii=False)}")

note(
    "五站各有分工，而**只有 analyze 同 advise 會問 LLM**；\n"
    "   另外三站（tools／guardrail／persist）全部係普通 Python —— 呢個就係「deterministic core」。\n"
    "   課程 §04 會逐站拆解，lab08 會示範 persist 嘅閘門。"
)
