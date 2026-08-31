"""RAG recall evaluation: hit rate of the expected source within top-k results."""
from app.rag.retrieve import retrieve


def evaluate_recall(session, scenarios: list[dict], embedder, top_k: int = 3) -> dict:
    hits = 0
    results = []
    for sc in scenarios:
        chunks = retrieve(session, sc["query"], embedder, top_k=top_k)
        sources = [c.source for c, _ in chunks]
        hit = sc["expected_source"] in sources
        if hit:
            hits += 1
        results.append({"id": sc["id"], "hit": hit, "sources": sources})
    recall = hits / len(scenarios) if scenarios else 0.0
    return {"recall": recall, "results": results}
