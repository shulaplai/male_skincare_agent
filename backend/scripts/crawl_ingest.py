"""Crawl the beauty seed list and ingest pages into the vector store.

Usage:
    HF_HOME=./.hf-cache python scripts/crawl_ingest.py
    SKINCOACH_SEED=./corpus/sources.txt  (default)
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db  # noqa: E402
from app.rag.crawler import content_hash, fetch_page  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402
from app.rag.ingest import ingest_text  # noqa: E402


def main() -> None:
    init_db()
    seed_file = os.environ.get("SKINCOACH_SEED", "./corpus/sources.txt")
    urls = [
        l.strip()
        for l in Path(seed_file).read_text().splitlines()
        if l.strip() and not l.startswith("#")
    ]

    embedder = FastembedEmbedder()
    session = SessionLocal()
    seen: set[str] = set()
    ok = 0
    for url in urls:
        page = fetch_page(url)
        if page is None:
            print(f"SKIP {url}")
            continue
        digest = content_hash(page["text"])
        if digest in seen:
            print(f"DUP  {url}")
            continue
        seen.add(digest)
        n = ingest_text(
            session,
            urlparse(url).netloc,
            page["text"],
            embedder,
            url=page["url"],
            title=page["title"],
        )
        ok += 1
        print(f"OK   {url} -> {n} chunks")
    session.close()
    print(f"done: {ok} pages ingested, {len(urls) - ok} skipped")


if __name__ == "__main__":
    main()
