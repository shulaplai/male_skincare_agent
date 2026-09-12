"""Agent evaluation: run golden scenarios through the graph and score them.

Checks (deterministic): expected escalation matches, expected keyword present,
expected tool actually produced rows, and the safety checks hold. Runs fine with
FakeLLM (no key) — and with a real LLM it is the gate that catches a model which
never asks for any tool (RAG/memory silently skipped).
"""
from app.agent.graph import build_graph
from app.agent.schemas import Advice

from .safety import check_safety


def run_agent_eval(
    scenarios: list[dict],
    session_factory,
    embedder,
    llm,
    conversation_id: str,
) -> list[dict]:
    graph = build_graph(llm=llm, session_factory=session_factory, embedder=embedder)
    results = []
    for sc in scenarios:
        res = graph.invoke(
            {"conversation_id": conversation_id, "user_text": sc["user_text"], "photo_paths": []}
        )
        advice = Advice(**res["advice"])
        violations = check_safety(advice, sc["user_text"])

        tools = {
            r["tool"]: len(r["result"]) if isinstance(r.get("result"), list) else None
            for r in res.get("tool_results", [])
        }
        tool_calls = list((res.get("analysis") or {}).get("tool_calls", []))

        passed = True
        if "expect_escalate" in sc and bool(sc["expect_escalate"]) != bool(res["escalate"]):
            passed = False
        if "expect_contains" in sc and sc["expect_contains"] not in " ".join(advice.items):
            passed = False
        if "expect_tool" in sc and not tools.get(sc["expect_tool"]):
            # 有要求跑但冇資料 rows、或者 model 根本冇叫過呢個 tool
            passed = False
        if violations:
            passed = False

        results.append(
            {
                "id": sc["id"],
                "passed": passed,
                "escalate": res["escalate"],
                "violations": violations,
                "advice": advice.items,
                "advice_items": advice.items,
                "user_text": sc["user_text"],
                "tool_calls": tool_calls,
                "tools": tools,
                "expect_tool": sc.get("expect_tool"),
            }
        )
    return results
