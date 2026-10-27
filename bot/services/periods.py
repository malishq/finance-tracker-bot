from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

TODAY = "today"
WEEK = "week"
MONTH = "month"

MONTHS_GENITIVE = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]
MONTHS_NOMINATIVE = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]
WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


@dataclass(frozen=True)
class Period:
    kind: str
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def local_now(tz_offset: int, now_utc: Optional[datetime] = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(timezone(timedelta(hours=tz_offset)))


def local_today(tz_offset: int, now_utc: Optional[datetime] = None) -> date:
    return local_now(tz_offset, now_utc).date()


def month_bounds(year: int, month: int) -> Tuple[date, date]:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def shift_month(year: int, month: int, delta: int) -> Tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def period_for(kind: str, today: date) -> Period:
    if kind == TODAY:
        return Period(kind, today, today)
    if kind == WEEK:
        start = today - timedelta(days=today.weekday())
        return Period(kind, start, start + timedelta(days=6))
    if kind == MONTH:
        start, end = month_bounds(today.year, today.month)
        return Period(kind, start, end)
    raise ValueError(f"Неизвестный период: {kind}")


def comparison_period(period: Period, today: date) -> Period:
    elapsed = max(0, min((today - period.start).days, period.days - 1))
    if period.kind == TODAY:
        return Period(period.kind, today - timedelta(days=1), today - timedelta(days=1))
    if period.kind == WEEK:
        start = period.start - timedelta(days=7)
        return Period(period.kind, start, start + timedelta(days=elapsed))
    year, month = shift_month(period.start.year, period.start.month, -1)
    start, last = month_bounds(year, month)
    end = min(last, start + timedelta(days=elapsed))
    return Period(period.kind, start, end)


def last_days(today: date, count: int) -> Period:
    return Period("range", today - timedelta(days=count - 1), today)


def format_day(value: date, with_year: bool = False) -> str:
    text = f"{value.day} {MONTHS_GENITIVE[value.month - 1]}"
    return f"{text} {value.year}" if with_year else text


def format_range(start: date, end: date) -> str:
    if start == end:
        return format_day(start)
    if start.month == end.month and start.year == end.year:
        return f"{start.day}–{end.day} {MONTHS_GENITIVE[start.month - 1]}"
    return f"{format_day(start)} – {format_day(end)}"


def period_title(period: Period, today: date) -> str:
    if period.kind == TODAY:
        if period.start == today:
            return f"Сегодня, {format_day(today)}"
        if period.start == today - timedelta(days=1):
            return f"Вчера, {format_day(period.start)}"
        return format_day(period.start)
    if period.kind == WEEK:
        return f"Неделя {format_range(period.start, period.end)}"
    if period.kind == MONTH:
        return f"{MONTHS_NOMINATIVE[period.start.month - 1]} {period.start.year}"
    return format_range(period.start, period.end)


def relative_day(value: date, today: date) -> str:
    if value == today:
        return "сегодня"
    if value == today - timedelta(days=1):
        return "вчера"
    return f"{value.day:02d}.{value.month:02d}" if value.year == today.year else value.strftime("%d.%m.%Y")
