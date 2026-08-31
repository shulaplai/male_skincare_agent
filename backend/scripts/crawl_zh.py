"""Crawl Chinese beauty websites using Playwright (JS rendering) + trafilatura.

Many HK/TW beauty portals render content client-side or sit behind anti-bot, so
plain httpx returns empty shells. This renders each page in headless Chromium,
then runs trafilatura on the rendered HTML.

Usage:
    HF_HOME=./.hf-cache python scripts/crawl_zh.py
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Chunk  # noqa: E402
from app.rag.crawler import USER_AGENT, content_hash  # noqa: E402
from app.rag.embeddings import FastembedEmbedder  # noqa: E402
from app.rag.ingest import ingest_text  # noqa: E402

SITES = [
    # (label, sitemap_url, url_path_keywords)
    ("lookin", "https://www.look-in.com.tw/sitemap.xml", ["/beauty/", "/fashion/"]),
    ("juksy", "https://www.juksy.com/sitemap.xml", []),
    ("popdaily", "https://www.popdaily.com.tw/sitemap.xml", []),
]

TITLE_KEYWORDS = [
    "護膚", "美肌", "暗瘡", "痤瘡", "保濕", "面膜", "防曬", "精華", "潔面", "洗面",
    "毛孔", "去印", "美白", "粉刺", "黑頭", "眼霜", "爽膚", "乳液", "化妝水", "皮膚",
    "敏感肌", "去角質", "淡斑", "控油", "酒糟", "玫瑰痤瘡", "泛紅", "緊緻", "抗老",
    "成份", "成分", "修護", "補水", "鎖水", "油光", "乾燥", "粗糙", "保養", "肌膚",
]
MAX_PAGES = 260


def collect_urls(sm_url: str, depth: int = 0) -> list[str]:
    r = httpx.get(sm_url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
    r.raise_for_status()
    locs = re.findall(r"<loc>(.*?)</loc>", r.text)
    out: list[str] = []
    for loc in locs:
        loc = loc.strip()
        if not loc:
            continue
        if loc.endswith(".xml"):
            if depth < 3:
                out.extend(collect_urls(loc, depth + 1))
        else:
            out.append(loc)
    return out


def extract(page, url: str) -> dict | None:
    html = page.content()
    text = trafilatura.extract(html, include_comments=False, include_tables=False)
    if not text or len(text.strip()) < 200:
        return None
    meta = trafilatura.extract_metadata(html)
    title = (meta.title or page.title() or "").strip() if meta else (page.title() or "")
    return {"url": url, "title": title, "text": text}


def main() -> None:
    init_db()
    session = SessionLocal()
    existing = {c.url for c in session.query(Chunk).all()}
    session.close()

    candidates: list[str] = []
    for label, sm_url, path_kw in SITES:
        try:
            urls = collect_urls(sm_url)
        except Exception as e:
            print(f"{label}: sitemap failed ({type(e).__name__})")
            continue
        if path_kw:
            urls = [u for u in urls if any(k in u.lower() for k in path_kw)]
        print(f"{label}: {len(urls)} candidate URLs")
        candidates.extend(urls)

    candidates = sorted({u for u in candidates if u not in existing})[:MAX_PAGES]
    print(f"total candidates: {len(candidates)}")

    embedder = FastembedEmbedder()
    from playwright.sync_api import sync_playwright

    session = SessionLocal()
    seen: set[str] = set()
    ok = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        for url in candidates:
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(1200)
                doc = extract(page, url)
            except Exception:
                doc = None
            if doc is None:
                continue
            if not any(k.lower() in doc["title"].lower() for k in TITLE_KEYWORDS):
                continue
            digest = content_hash(doc["text"])
            if digest in seen:
                continue
            seen.add(digest)
            ingest_text(
                session,
                urlparse(url).netloc,
                doc["text"],
                embedder,
                url=doc["url"],
                title=doc["title"],
            )
            ok += 1
            if ok >= 200:
                break
        browser.close()
    session.close()
    print(f"done: {ok} Chinese pages ingested")


if __name__ == "__main__":
    main()
