from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import UserSettings
from .periods import local_now

WINDOW_MINUTES = 10


def reminder_due(user: UserSettings, now_utc: datetime, window_minutes: int = WINDOW_MINUTES) -> Optional[str]:
    if not user.reminder_time:
        return None
    local = local_now(user.tz_offset, now_utc)
    today = local.date().isoformat()
    if user.last_reminder_date == today:
        return None
    try:
        hours, minutes = (int(part) for part in user.reminder_time.split(":"))
    except ValueError:
        return None
    target = local.replace(hour=hours, minute=minutes, second=0, microsecond=0)
    passed = (local - target).total_seconds()
    if 0 <= passed < window_minutes * 60:
        return today
    return None
