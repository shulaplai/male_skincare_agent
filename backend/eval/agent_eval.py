"""Agent evaluation: run golden scenarios through the graph and score them.

Checks (deterministic): expected escalation matches, expected keyword present,
expected tool actually produced rows, and the safety checks hold. Runs fine with
FakeLLM (no key) — and with a real LLM it is the gate that catches a model which
never asks for any tool (RAG/memory silently skipped).

⚠️ **Scenario isolation (fixed 2026-09)**: each scenario gets its OWN conversation.
The graph ends in `persist`, so sharing one conversation made the scenarios
order-dependent. Measured before the fix, on the three committed scenarios:

    #1 first_checkin=True   insights=3  max_conf=0.600  recent_msgs=0  get_skin_profile_rows=0
    #2 first_checkin=False  insights=3  max_conf=0.650  recent_msgs=2  get_skin_profile_rows=3
    #3 first_checkin=False  insights=3  max_conf=0.700  recent_msgs=4  get_skin_profile_rows=3

i.e. scenarios 2-3 never reached the `first_checkin` onboarding branch, memory
confidence climbed purely from running more scenarios, and the rows that satisfied
"the tool returned data" were the previous scenario's. With FakeLLM (constant
output) no PASS/FAIL flips, so CI stayed green — the gate looked healthy while
measuring the wrong thing. Adding, removing or reordering a scenario changed the
others' results.

Isolation alone would *lose* the "coach already has memory" path (it was only ever
hit by accident), so a scenario can now ask for it explicitly with `seed_days`.
"""
import datetime

from app.agent.attributes import describe_attribute, direction_for
from app.agent.graph import build_graph
from app.agent.schemas import Advice
from app.memory import expiry_for, make_derived
from app.models import Entry, Insight, new_id, utcnow

from .safety import check_safety

# Seeded history has to be severe enough that the attributes describe a problem,
# otherwise `get_skin_profile` returns rows that say nothing.
_SEED_ATTRIBUTES = [("acne", 2), ("oiliness", 2)]


def _seed_history(session_factory, conversation_id: str, days: int) -> None:
    """Write `days` past Entries + matching derived insights for a scenario.

    Mirrors what `graph.persist` would have produced on those days, so a scenario
    can exercise the populated-memory path *deliberately* instead of leaking it
    from whichever scenario happened to run first.
    """
    session = session_factory()
    try:
        today = datetime.date.today()
        for i in range(1, days + 1):
            session.add(
                Entry(
                    conversation_id=conversation_id,
                    date=today - datetime.timedelta(days=i),
                    note=f"（eval seed）第 {i} 日",
                    attributes=[
                        {"key": key, "severity": sev, "note": ""} for key, sev in _SEED_ATTRIBUTES
                    ],
                )
            )
        now = utcnow()
        for key, sev in _SEED_ATTRIBUTES:
            m = make_derived(
                new_id(), key, describe_attribute(key, sev), 0.6, now, direction=direction_for(sev)
            )
            session.add(
                Insight(
                    conversation_id=conversation_id,
                    kind=m.kind,
                    tag=m.tag,
                    direction=m.direction,
                    text=m.text,
                    confidence=m.confidence,
                    expires_at=m.expires_at,
                    version=m.version,
                )
            )
        session.commit()
    finally:
        session.close()


def run_agent_eval(
    scenarios: list[dict],
    session_factory,
    embedder,
    llm,
    make_conversation,
) -> list[dict]:
    """Score golden scenarios. `make_conversation()` returns a fresh conversation id.

    One conversation per scenario — see the module docstring for why.
    """
    graph = build_graph(llm=llm, session_factory=session_factory, embedder=embedder)
    results = []
    for sc in scenarios:
        conversation_id = make_conversation()
        seed_days = int(sc.get("seed_days") or 0)
        if seed_days:
            _seed_history(session_factory, conversation_id, seed_days)

        res = graph.invoke(
            {
                "conversation_id": conversation_id,
                "user_text": sc["user_text"],
                "photo_paths": [],
                # Production `service.run_consult` always supplies this; without it
                # the eval ran a differently-shaped initial state than the product
                # (`analyze` reads state.get("cloud_analysis")).
                "cloud_analysis": False,
            }
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
                # Isolation evidence: every scenario should report True here.
                "first_checkin": bool(res.get("first_checkin")),
                "seed_days": seed_days,
            }
        )
    return results
