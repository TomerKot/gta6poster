from __future__ import annotations

from html import escape

from .models import Item

TG_LIMIT = 4096


def build_message(item: Item) -> str:
    """Telegram HTML. Весь зовнішній текст екранується — ін'єкція розмітки неможлива."""
    parts: list[str] = []
    if item.rumor:
        parts.append("⚠️ <i>Неперевірена інформація / чутки</i>")
    parts.append(f"<b>{escape(item.title[:250], quote=False)}</b>")
    if item.summary:
        parts.append(escape(item.summary, quote=False))
    href = escape(item.url, quote=True)
    parts.append(f'🔗 <a href="{href}">{escape(item.source, quote=False)}</a>')
    msg = "\n\n".join(parts)
    return msg[:TG_LIMIT]
