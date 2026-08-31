"""Corpus ingestion: PDF / JATS XML / text -> text -> chunks -> embeddings -> store."""
import io
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy.orm import Session

from .chunking import chunk_text
from .embeddings import Embedder
from .vectorstore import add_chunks


def extract_text_from_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def extract_text_from_jats_xml(data: bytes) -> str:
    """Pull paragraph/title text out of a JATS XML article (Europe PMC full text)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return ""
    parts: list[str] = []
    for el in root.iter():
        if el.tag in ("p", "title", "abstract", "article-title"):
            text = "".join(el.itertext()).strip()
            if text:
                parts.append(text)
    return "\n".join(parts)


def ingest_text(session: Session, source: str, text: str, embedder: Embedder) -> int:
    chunks = chunk_text(text)
    items = [(c, embedder.embed(c)) for c in chunks]
    return add_chunks(session, source, items)


def ingest_pdf(session: Session, source: str, data: bytes, embedder: Embedder) -> int:
    return ingest_text(session, source, extract_text_from_pdf(data), embedder)


def ingest_file(session: Session, path: str | Path, embedder: Embedder) -> int:
    p = Path(path)
    data = p.read_bytes()
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        text = extract_text_from_pdf(data)
    elif suffix == ".xml":
        text = extract_text_from_jats_xml(data)
    else:  # .txt / .md / plain text
        text = data.decode("utf-8", errors="replace")
    return ingest_text(session, p.name, text, embedder)
