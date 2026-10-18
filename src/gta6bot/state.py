from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

KEEP_DAYS = 30
MAX_ENTRIES = 5000


def load(path: Path) -> dict | None:
    """None = файлу немає (перший запуск)."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = {}
    data.setdefault("urls", {})
    data.setdefault("titles", {})
    return data


def new_state() -> dict:
    return {"version": 1, "urls": {}, "titles": {}, "heartbeat": ""}


def prune(state: dict, now: datetime) -> None:
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    for key in ("urls", "titles"):
        d = {k: v for k, v in state[key].items() if v >= cutoff}
        if len(d) > MAX_ENTRIES:
            d = dict(sorted(d.items(), key=lambda kv: kv[1])[-MAX_ENTRIES:])
        state[key] = d


def save(path: Path, state: dict, now: datetime) -> None:
    prune(state, now)
    # heartbeat міняється раз на місяць: коміт тримає репозиторій "живим",
    # інакше GitHub вимикає cron після 60 днів без активності.
    state["heartbeat"] = now.strftime("%Y-%m")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)
