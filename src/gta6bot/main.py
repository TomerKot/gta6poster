from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import tomllib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import filters, formatting, state as st
from .models import Item

log = logging.getLogger("gta6bot")


def collect(cfg: dict, now: datetime) -> list[Item]:
    from .fetch import fetch_source  # імпорт тут, щоб тести не вимагали мережевих залежностей

    s = cfg["settings"]
    keywords = filters.compile_patterns(cfg["filters"]["keywords"])
    blocked = filters.compile_patterns(cfg["filters"]["block"])
    rumors = filters.compile_patterns(cfg["filters"]["rumor"])
    max_age = timedelta(hours=s["max_age_hours"])

    out: list[Item] = []
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            items = fetch_source(src, s["snippet_chars"])
        except Exception as exc:  # одне зламане джерело не має зупиняти решту
            log.warning("source '%s' failed: %s", src["name"], type(exc).__name__)
            continue
        kept = 0
        for it in items:
            text = f"{it.title} {it.summary}"
            if src.get("requires_keyword", True) and not filters.matches_any(text, keywords):
                continue
            if filters.matches_any(text, blocked):
                log.info("blocked: %s", it.title[:80])
                continue
            if it.published and now - it.published > max_age:
                continue
            it.rumor = filters.matches_any(text, rumors)
            out.append(it)
            kept += 1
        log.info("source '%s': %d fetched, %d relevant", src["name"], len(items), kept)
    return out


def run(args: argparse.Namespace) -> int:
    cfg = tomllib.loads(Path(args.config).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    state_path = Path(args.state)
    state = st.load(state_path)
    first_run = state is None
    if first_run:
        state = st.new_state()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not args.dry_run and not (token and chat_id):
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set")
        return 2

    # дедуплікація: за URL (між запусками) і за заголовком (між джерелами)
    fresh: list[Item] = []
    run_titles: set[str] = set()
    for it in collect(cfg, now):
        uh, th = filters.digest(it.url), filters.title_key(it.title)
        if uh in state["urls"]:
            continue
        if th in state["titles"] or th in run_titles:
            state["urls"][uh] = now.isoformat()
            continue
        run_titles.add(th)
        fresh.append(it)

    if first_run and not args.post_initial:
        for it in fresh:
            state["urls"][filters.digest(it.url)] = now.isoformat()
            state["titles"][filters.title_key(it.title)] = now.isoformat()
        log.info("first run: seeded %d items, nothing posted", len(fresh))
        if not args.dry_run:
            st.save(state_path, state, now)
        return 0

    far = datetime.min.replace(tzinfo=timezone.utc)
    fresh.sort(key=lambda i: (not i.official, i.published or far))
    limit = cfg["settings"]["max_posts_per_run"]
    pause = cfg["settings"]["seconds_between_posts"]
    posted = failures = 0
    try:
        for it in fresh[:limit]:
            msg = formatting.build_message(it)
            if args.dry_run:
                print("-----\n" + msg)
                continue
            from .telegram import send

            if send(token, chat_id, msg, it.url):
                state["urls"][filters.digest(it.url)] = now.isoformat()
                state["titles"][filters.title_key(it.title)] = now.isoformat()
                posted += 1
                failures = 0
                time.sleep(pause)
            else:
                failures += 1
                if failures >= 2:
                    log.error("two failures in a row, aborting run")
                    return 1
    finally:
        if not args.dry_run:
            st.save(state_path, state, now)
    log.info("done: %d candidates, %d posted", len(fresh), posted)
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.toml")
    ap.add_argument("--state", default="state/seen.json")
    ap.add_argument("--dry-run", action="store_true", default=os.environ.get("DRY_RUN") == "1")
    ap.add_argument("--post-initial", action="store_true", help="не пропускати перший запуск")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(args))


if __name__ == "__main__":
    main()
