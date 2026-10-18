from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Item:
    title: str
    url: str            # канонічний URL (вже очищений)
    summary: str        # очищений від HTML короткий опис
    published: datetime | None
    source: str
    official: bool = False
    rumor: bool = False
