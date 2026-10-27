from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _parse_ids(raw: str) -> List[int]:
    ids = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            ids.append(int(part))
    return ids


@dataclass
class Config:
    bot_token: str
    admin_ids: List[int] = field(default_factory=list)
    db_path: str = "data/finance.db"
    default_currency: str = "₽"
    default_tz_offset: int = 3
    log_level: str = "INFO"


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN: скопируйте .env.example в .env и впишите токен")
    db_path = os.getenv("DB_PATH", "data/finance.db").strip() or "data/finance.db"
    if not os.path.isabs(db_path):
        db_path = str(BASE_DIR / db_path)
    try:
        tz_offset = int(os.getenv("DEFAULT_TZ_OFFSET", "3"))
    except ValueError:
        tz_offset = 3
    return Config(
        bot_token=token,
        admin_ids=_parse_ids(os.getenv("ADMIN_IDS", "")),
        db_path=db_path,
        default_currency=os.getenv("DEFAULT_CURRENCY", "₽").strip() or "₽",
        default_tz_offset=tz_offset,
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
