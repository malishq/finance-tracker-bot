from datetime import datetime, timezone

from bot.services.models import UserSettings
from bot.services.reminders import reminder_due


def user(**kwargs):
    base = {"user_id": 1, "currency": "₽", "tz_offset": 3, "reminder_time": "21:00", "last_reminder_date": None}
    base.update(kwargs)
    return UserSettings(**base)


def test_due_inside_window_in_local_time():
    now = datetime(2026, 10, 28, 18, 3, tzinfo=timezone.utc)
    assert reminder_due(user(), now) == "2026-10-28"


def test_not_due_before_time_or_after_window():
    assert reminder_due(user(), datetime(2026, 10, 28, 17, 59, tzinfo=timezone.utc)) is None
    assert reminder_due(user(), datetime(2026, 10, 28, 18, 11, tzinfo=timezone.utc)) is None


def test_not_repeated_same_day_and_disabled():
    now = datetime(2026, 10, 28, 18, 3, tzinfo=timezone.utc)
    assert reminder_due(user(last_reminder_date="2026-10-28"), now) is None
    assert reminder_due(user(last_reminder_date="2026-10-27"), now) == "2026-10-28"
    assert reminder_due(user(reminder_time=None), now) is None


def test_offset_changes_local_day():
    now = datetime(2026, 10, 28, 23, 30, tzinfo=timezone.utc)
    assert reminder_due(user(tz_offset=5, reminder_time="04:30"), now) == "2026-10-29"
