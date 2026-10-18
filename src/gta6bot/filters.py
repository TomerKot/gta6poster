"""Чисті функції: очищення тексту, канонізація URL, фільтри. Без мережі."""
from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "ref", "ref_src", "mc_cid", "mc_eid", "cmpid"}


class _Stripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def clean_text(raw: str, limit: int) -> str:
    """HTML -> простий текст, схлопнуті пробіли, обрізка по межі слова."""
    if not raw:
        return ""
    s = _Stripper()
    try:
        s.feed(raw[:20000])
    except Exception:  # зламаний HTML не повинен валити весь запуск
        return ""
    text = re.sub(r"\s+", " ", "".join(s.parts)).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:!?—- ")
    return cut + "…"


def canonical_url(url: str) -> str | None:
    """Лишає тільки http(s), прибирає трекінг і фрагмент. Інакше -> None."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return None
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/", urlencode(query), ""))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def title_key(title: str) -> str:
    words = re.findall(r"[\w]+", title.lower())
    return digest(" ".join(words))


def compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def matches_any(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)
