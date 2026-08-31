"""RAG retrieval evaluation: recall@k and MRR over golden queries."""
from app.rag.retrieve import retrieve


def evaluate_recall(session, scenarios: list[dict], embedder, top_k: int = 3) -> dict:
    hits = 0
    mrr = 0.0
    results = []
    for sc in scenarios:
        chunks = retrieve(session, sc["query"], embedder, top_k=top_k)
        sources = [c.source for c, _ in chunks]
        rank = None
        for i, s in enumerate(sources, start=1):
            if sc["expected_source"] in s:
                rank = i
                break
        hit = rank is not None
        if hit:
            hits += 1
            mrr += 1.0 / rank
        results.append({"id": sc["id"], "hit": hit, "rank": rank, "sources": sources})
    n = len(scenarios) or 1
    return {"recall": hits / n, "mrr": mrr / n, "results": results}
