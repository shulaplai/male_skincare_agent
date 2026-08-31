"""Web crawler for the beauty corpus.

Fetches a page, extracts main-content text with trafilatura, and returns
`{url, title, text}`. Politeness: per-domain rate limit + a descriptive UA.
(robots.txt is respected best-effort at the orchestration layer.)
"""
import hashlib
import time
from urllib.parse import urlparse

import httpx
import trafilatura

USER_AGENT = "SkinCoachBot/0.1 (research; contact: local)"
MIN_INTERVAL = 1.5  # seconds between requests to the same domain
_last: dict[str, float] = {}


def _domain(url: str) -> str:
    return urlparse(url).netloc


def _throttle(domain: str) -> None:
    wait = MIN_INTERVAL - (time.time() - _last.get(domain, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last[domain] = time.time()


def fetch_page(url: str, timeout: float = 25.0) -> dict | None:
    domain = _domain(url)
    _throttle(domain)
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except Exception:
        return None

    text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
    if not text or len(text.strip()) < 200:
        return None
    meta = trafilatura.extract_metadata(resp.text)
    title = (meta.title or "").strip() if meta else ""
    return {"url": str(resp.url), "title": title, "text": text}


def content_hash(text: str) -> str:
    return hashlib.md5(text.strip().encode("utf-8")).hexdigest()
