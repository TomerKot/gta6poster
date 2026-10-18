from __future__ import annotations

import logging
from calendar import timegm
from datetime import datetime, timezone

import feedparser
import requests

from .filters import canonical_url, clean_text
from .models import Item

log = logging.getLogger(__name__)

MAX_BYTES = 2_000_000
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; gta6-news-bot/1.0)"}


def _download(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("only https feeds are allowed")
    with requests.get(url, headers=HEADERS, timeout=(5, 15), stream=True) as r:
        r.raise_for_status()
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > MAX_BYTES:
                raise ValueError("feed too large")
        return bytes(buf)


def fetch_source(src: dict, snippet_chars: int) -> list[Item]:
    """Тягне один фід. Дані з інтернету вважаються недовіреними."""
    parsed = feedparser.parse(_download(src["url"]))
    items: list[Item] = []
    for e in parsed.entries[:60]:
        url = canonical_url(e.get("link", ""))
        title = clean_text(e.get("title", ""), 250)
        if not url or not title:
            continue
        ts = e.get("published_parsed") or e.get("updated_parsed")
        published = datetime.fromtimestamp(timegm(ts), tz=timezone.utc) if ts else None
        items.append(
            Item(
                title=title,
                url=url,
                summary=clean_text(e.get("summary", ""), snippet_chars),
                published=published,
                source=src["name"],
                official=bool(src.get("official", False)),
            )
        )
    return items
