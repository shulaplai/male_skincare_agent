"""Eval harness runner: RAG recall + agent golden scenarios + safety (+ judge).

Isolation (Q16): everything runs on a throwaway SQLite database seeded from the
committed golden corpus in `eval/golden/` — the real dev DB is never touched,
so results are reproducible from a clean clone.

Usage:
    HF_HOME=./.hf-cache python -m eval.run_eval            # real embedder/LLM
    python -m eval.run_eval --fake                          # deterministic, no network (CI)

`--fake` uses FakeLLM + the hashing embedder so CI gets stable numbers without
downloading models or calling paid APIs. Exit code is non-zero if anything FAILs
(CI gate: "eval 綠先 merge").
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models  # noqa: E402,F401  (register tables on Base.metadata)
from app.agent.llm import FakeLLM, get_llm  # noqa: E402
from app.db import Base  # noqa: E402
from app.rag import DeterministicEmbedder, FastembedEmbedder, ingest_file  # noqa: E402
from eval.agent_eval import run_agent_eval  # noqa: E402
from eval.judge import judge_advice  # noqa: E402
from eval.rag_recall import evaluate_recall  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"


def build_embedder(fake: bool):
    if fake:
        return DeterministicEmbedder()
    return FastembedEmbedder()


def ingest_golden(session, embedder) -> int:
    total = 0
    for p in sorted(GOLDEN_DIR.glob("*.txt")):
        total += ingest_file(session, p, embedder)
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Deterministic mode for CI: FakeLLM + hashing embedder (no network, no key).",
    )
    args = parser.parse_args()

    here = Path(__file__).parent
    rag_scenarios = json.loads((here / "rag_scenarios.json").read_text())
    scenarios = json.loads((here / "scenarios.json").read_text())

    embedder = build_embedder(args.fake)
    llm = FakeLLM() if args.fake else get_llm("text")

    # Throwaway DB: temp file (so in-memory table counts behave), removed after.
    tmp = tempfile.NamedTemporaryFile(prefix="skincoach_eval_", suffix=".db", delete=False)
    tmp.close()
    tmp_path = tmp.name
    try:
        engine = create_engine(f"sqlite:///{tmp_path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        session = Session()
        n_chunks = ingest_golden(session, embedder)
        from app import crud  # noqa: E402

        conv = crud.create_conversation(session, "面部皮膚", "🧔")
        cid = conv.id
        session.close()

        # 1) RAG recall@3 + MRR over the committed golden corpus.
        session = Session()
        recall = evaluate_recall(session, rag_scenarios, embedder)
        session.close()

        # 2) Agent golden scenarios through the real graph (deterministic gates).
        agent_results = run_agent_eval(scenarios, Session, embedder, llm, cid)

        # 3) LLM-as-judge (Q17): only with a real key configured.
        judge_scores = None
        if not args.fake and not isinstance(get_llm("text"), FakeLLM):
            judge_scores = []
            for r in agent_results:
                v = judge_advice(r["user_text"], r["advice_items"])
                if v is not None:
                    judge_scores.append(
                        {
                            "id": r["id"],
                            "specificity": v.specificity,
                            "relevance": v.relevance,
                            "safety": v.safety,
                        }
                    )

        lines = ["# SkinCoach Eval Report", ""]
        lines.append(f"（golden corpus：{n_chunks} chunks · {'fake' if args.fake else 'real'} mode）")
        lines.append("")
        lines.append(f"## RAG recall@{recall['top_k']}: {recall['recall'] * 100:.0f}% · MRR: {recall['mrr']:.2f}")
        for r in recall["results"]:
            lines.append(f"- {r['id']}: {'PASS' if r['hit'] else 'FAIL'} (rank={r['rank']})")
        lines.append("")
        lines.append("## Agent scenarios")
        for r in agent_results:
            mark = "PASS" if r["passed"] else "FAIL"
            lines.append(f"- {r['id']}: {mark} (escalate={r['escalate']}, violations={r['violations']})")

        if judge_scores is not None:
            lines.append("")
            lines.append("## LLM-as-judge（1–5 分）")
            for j in judge_scores:
                lines.append(
                    f"- {j['id']}: 具體性 {j['specificity']} / 相關性 {j['relevance']} / 安全 {j['safety']}"
                )
        elif args.fake:
            lines.append("")
            lines.append("（--fake mode：唔跑 LLM-as-judge）")

        report = "\n".join(lines) + "\n"
        out = here / "out"
        out.mkdir(exist_ok=True)
        (out / "report.md").write_text(report)
        print(report)

        failed = any(not r["hit"] for r in recall["results"]) or any(
            not r["passed"] for r in agent_results
        )
        sys.exit(1 if failed else 0)
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    main()
