from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

EXPENSE = "expense"
INCOME = "income"


@dataclass
class Entry:
    id: int
    kind: str
    amount: int
    category: str
    description: str
    entry_date: date


@dataclass
class UserSettings:
    user_id: int
    currency: str = "₽"
    tz_offset: int = 3
    reminder_time: Optional[str] = None
    last_reminder_date: Optional[str] = None
