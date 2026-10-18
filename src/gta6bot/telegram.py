from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)
API = "https://api.telegram.org/bot{token}/sendMessage"


def send(token: str, chat_id: str, text: str, preview_url: str) -> bool:
    """Публікує повідомлення. Токен НІКОЛИ не потрапляє в логи:
    винятки requests містять URL з токеном, тому логуємо лише тип помилки."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "link_preview_options": {"url": preview_url, "prefer_large_media": True},
    }
    for attempt in range(3):
        try:
            r = requests.post(API.format(token=token), json=payload, timeout=20)
        except requests.RequestException as exc:
            log.warning("Telegram network error: %s", type(exc).__name__)
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code == 200:
            return True
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code == 429:
            wait = int(body.get("parameters", {}).get("retry_after", 5))
            if wait > 30:
                log.error("Telegram rate limit too long (%ss), stopping", wait)
                return False
            time.sleep(wait + 1)
            continue
        if r.status_code >= 500:
            time.sleep(2 * (attempt + 1))
            continue
        log.error("Telegram rejected message: %s %s", r.status_code, body.get("description", ""))
        return False
    return False
