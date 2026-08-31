"""Ingest the corpus into the vector store.

Scans both the committed seed corpus (`./corpus`) and downloaded files
(`./data/corpus`). Override with SKINCOACH_CORPUS_DIRS (colon-separated).

Usage:
    python scripts/ingest_corpus.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db  # noqa: E402
from app.rag import ingest_file  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402

DEFAULT_DIRS = "./corpus:./data/corpus"


def main() -> None:
    init_db()
    dirs = os.environ.get("SKINCOACH_CORPUS_DIRS", DEFAULT_DIRS).split(":")
    embedder = FastembedEmbedder()
    session = SessionLocal()
    total = 0
    for d in dirs:
        for p in sorted(Path(d).glob("*")):
            if p.name == "sources.txt":  # URL seed list, not content
                continue
            if p.suffix.lower() in (".pdf", ".xml", ".txt", ".md"):
                n = ingest_file(session, p, embedder)
                print(f"ingested {p}: {n} chunks")
                total += n
    session.close()
    print(f"total chunks: {total}")


if __name__ == "__main__":
    main()
