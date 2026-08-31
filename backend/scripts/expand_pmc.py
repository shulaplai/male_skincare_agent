"""Bulk-ingest open-access skincare/dermatology full text from Europe PMC.

Reliable, license-clean (open access) way to reach 200+ sources: query the REST
API for open-access articles with full text, then fetch each fullTextXML.

Usage:
    HF_HOME=./.hf-cache python scripts/expand_pmc.py
"""
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Chunk  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402
from app.rag.ingest import extract_text_from_jats_xml, ingest_text  # noqa: E402

QUERY = (
    "(acne OR rosacea OR dermatitis OR hyperpigmentation OR melasma OR "
    '"skin barrier" OR retinoid OR sunscreen OR niacinamide OR "salicylic acid") '
    "AND OPEN_ACCESS:Y AND HAS_FT:Y"
)
MAX_ARTICLES = 150
BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def main() -> None:
    init_db()
    r = httpx.get(
        f"{BASE}/search",
        params={"query": QUERY, "format": "json", "pageSize": 1000, "resultType": "core"},
        timeout=40,
    )
    r.raise_for_status()
    hits = r.json()["resultList"]["result"]
    print(f"search returned {len(hits)} articles")

    session = SessionLocal()
    existing = {c.source for c in session.query(Chunk).all()}
    session.close()

    embedder = FastembedEmbedder()
    session = SessionLocal()
    ok = 0
    for art in hits[:MAX_ARTICLES]:
        pmcid = art.get("pmcid")
        title = (art.get("title") or "").strip()
        if not pmcid or pmcid in existing:
            continue
        try:
            xr = httpx.get(f"{BASE}/{pmcid}/fullTextXML", timeout=40)
            if xr.status_code != 200:
                continue
        except Exception:
            continue
        text = extract_text_from_jats_xml(xr.content)
        if not text or len(text) < 500:
            continue
        ingest_text(session, pmcid, text, embedder, url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/", title=title)
        ok += 1
        if ok % 20 == 0:
            print(f"... {ok} articles so far")
        time.sleep(0.3)
    session.close()
    print(f"done: {ok} articles ingested")


if __name__ == "__main__":
    main()
