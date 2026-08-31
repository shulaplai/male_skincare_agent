"""Expand the corpus by crawling DermNet NZ's skincare-relevant topic pages.

Fetches the topic index, extracts topic slugs, filters to skincare keywords,
skips already-ingested URLs, then crawls + ingests the rest (rate-limited).

Usage:
    HF_HOME=./.hf-cache python scripts/expand_dermnet.py
"""
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Chunk  # noqa: E402
from app.rag.crawler import USER_AGENT, content_hash, fetch_page  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402
from app.rag.ingest import ingest_text  # noqa: E402

INDEX = "https://dermnetnz.org/topics"
MAX_PAGES = 200

SKIN_KEYWORDS = [
    "acne", "rosacea", "dermatitis", "eczema", "moisturis", "emollient", "sunscreen",
    "barrier", "sebum", "hyperpigmentation", "melasma", "retin", "niacinamide",
    "salicylic", "hyaluronic", "vitamin-c", "azelaic", "panthenol", "glycerin",
    "ceramide", "squalane", "benzoyl", "comedo", "dry-skin", "oily-skin",
    "sensitive-skin", "skin-care", "cleanser", "exfoliat", "pimple", "blackhead",
]


def main() -> None:
    init_db()
    resp = httpx.get(
        INDEX, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30
    )
    resp.raise_for_status()
    slugs = sorted(set(re.findall(r'href="/topics/([a-z0-9-]+)"', resp.text)))
    chosen = [s for s in slugs if any(k in s for k in SKIN_KEYWORDS)]
    print(f"index: {len(slugs)} topics, filtered skincare-relevant: {len(chosen)}")

    session = SessionLocal()
    existing = {c.url for c in session.query(Chunk).filter(Chunk.url.like("https://dermnetnz.org%")).all()}
    session.close()

    to_crawl = [f"https://dermnetnz.org/topics/{s}" for s in chosen if f"https://dermnetnz.org/topics/{s}" not in existing][:MAX_PAGES]
    print(f"to crawl: {len(to_crawl)}")

    embedder = FastembedEmbedder()
    session = SessionLocal()
    seen: set[str] = set()
    ok = 0
    for url in to_crawl:
        page = fetch_page(url)
        if page is None:
            continue
        digest = content_hash(page["text"])
        if digest in seen:
            continue
        seen.add(digest)
        ingest_text(session, "dermnetnz.org", page["text"], embedder, url=page["url"], title=page["title"])
        ok += 1
        if ok % 25 == 0:
            print(f"... {ok} pages so far")
    session.close()
    print(f"done: {ok} new pages ingested")


if __name__ == "__main__":
    main()
