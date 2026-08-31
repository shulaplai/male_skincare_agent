"""Agent evaluation: run golden scenarios through the graph and score them.

Checks (deterministic): expected escalation matches, expected keyword present,
and the safety checks hold. This runs fine with FakeLLM (no key).
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

        passed = True
        if "expect_escalate" in sc and bool(sc["expect_escalate"]) != bool(res["escalate"]):
            passed = False
        if "expect_contains" in sc and sc["expect_contains"] not in " ".join(advice.items):
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
            }
        )
    return results
