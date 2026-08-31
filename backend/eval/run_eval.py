"""Eval harness runner: RAG recall + agent golden scenarios + safety.

Usage:
    HF_HOME=./.hf-cache python -m eval.run_eval
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import crud  # noqa: E402
from app.agent.llm import get_llm  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402
from eval.agent_eval import run_agent_eval  # noqa: E402
from eval.rag_recall import evaluate_recall  # noqa: E402


def main() -> None:
    init_db()
    here = Path(__file__).parent
    rag_scenarios = json.loads((here / "rag_scenarios.json").read_text())
    scenarios = json.loads((here / "scenarios.json").read_text())

    embedder = FastembedEmbedder()
    llm = get_llm()

    session = SessionLocal()
    recall = evaluate_recall(session, rag_scenarios, embedder)
    conv = crud.create_conversation(session, "面部皮膚", "🧔")
    cid = conv.id
    session.close()

    agent_results = run_agent_eval(scenarios, SessionLocal, embedder, llm, cid)

    lines = ["# SkinCoach Eval Report", ""]
    lines.append(f"## RAG recall@3: {recall['recall'] * 100:.0f}%")
    for r in recall["results"]:
        lines.append(f"- {r['id']}: {'PASS' if r['hit'] else 'FAIL'}")
    lines.append("")
    lines.append("## Agent scenarios")
    for r in agent_results:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"- {r['id']}: {mark} (escalate={r['escalate']}, violations={r['violations']})")

    out = here / "out"
    out.mkdir(exist_ok=True)
    report = "\n".join(lines) + "\n"
    (out / "report.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
