from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

from .models import EXPENSE, INCOME

MAX_AMOUNT_MINOR = 1_000_000_000 * 100

NUMBER = r"(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d{1,2}))?"
SUFFIX = r"(?:\s*(?:([кk])|(тыс\.?)|руб\.?|р\.|р|₽|rub)(?![а-яёa-z]))?"
AMOUNT_RE = re.compile(r"(?<![\w.,])([+\-−–])?\s*" + NUMBER + SUFFIX + r"(?!\d)", re.IGNORECASE)
DATE_RE = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})(?:\.(\d{2}|\d{4}))?(?![\d.,а-яёa-z₽$€])", re.IGNORECASE)
WORD_DATES = {"сегодня": 0, "вчера": 1, "позавчера": 2}
INCOME_WORDS = (
    "зарплат", "зп", "аванс", "преми", "стипенди", "дивиденд", "кэшбэк", "кешбэк", "кэшбек", "кешбек",
    "подработк", "фриланс", "гонорар", "получк", "отпускн",
)


class ParseError(ValueError):
    pass


@dataclass
class ParsedEntry:
    amount: int
    kind: str
    description: str
    entry_date: date
    explicit_sign: bool


def _to_minor(whole: str, cents: Optional[str], thousands: bool) -> int:
    whole_value = int(whole.replace(" ", "").replace(" ", ""))
    cents_value = 0
    if cents:
        cents_value = int(cents) * 10 if len(cents) == 1 else int(cents)
    minor = whole_value * 100 + cents_value
    if thousands:
        minor *= 1000
    return minor


def parse_amount(text: str) -> int:
    match = AMOUNT_RE.search(text.strip())
    if not match:
        raise ParseError("Не нашёл сумму")
    minor = _to_minor(match.group(2), match.group(3), bool(match.group(4) or match.group(5)))
    if minor <= 0:
        raise ParseError("Сумма должна быть больше нуля")
    if minor > MAX_AMOUNT_MINOR:
        raise ParseError("Слишком большая сумма")
    return minor


def _resolve_date(match: "re.Match", today: date) -> Optional[date]:
    day, month, year_raw = int(match.group(1)), int(match.group(2)), match.group(3)
    if year_raw is None:
        year = today.year
    elif len(year_raw) == 2:
        year = 2000 + int(year_raw)
    else:
        year = int(year_raw)
    try:
        value = date(year, month, day)
    except ValueError:
        return None
    if year_raw is None and value > today:
        try:
            value = date(year - 1, month, day)
        except ValueError:
            return None
    return value


def _extract_date(text: str, today: date) -> Tuple[Optional[date], str]:
    lowered = text.lower()
    for word, days_ago in WORD_DATES.items():
        pattern = re.compile(r"(?<![\wа-яё])" + word + r"(?![\wа-яё])", re.IGNORECASE)
        found = pattern.search(lowered)
        if found:
            rest = text[: found.start()] + " " + text[found.end():]
            return today - timedelta(days=days_ago), rest
    for match in reversed(list(DATE_RE.finditer(text))):
        rest = text[: match.start()] + " " + text[match.end():]
        if not AMOUNT_RE.search(rest):
            continue
        value = _resolve_date(match, today)
        if value is not None:
            return value, rest
    return None, text


def _clean_description(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" ,.;:-–—")
    return text[:120]


def _looks_like_income(description: str) -> bool:
    words = re.findall(r"[а-яёa-z]+", description.lower().replace("ё", "е"))
    for word in words:
        for stem in INCOME_WORDS:
            if word == stem or (len(stem) >= 4 and word.startswith(stem)):
                return True
    return False


def parse_entry(text: str, today: Optional[date] = None) -> ParsedEntry:
    today = today or date.today()
    source = text.strip()
    if not source:
        raise ParseError("Пустое сообщение")
    entry_date, rest = _extract_date(source, today)
    match = AMOUNT_RE.search(rest)
    if not match:
        raise ParseError("Не нашёл сумму")
    minor = _to_minor(match.group(2), match.group(3), bool(match.group(4) or match.group(5)))
    if minor <= 0:
        raise ParseError("Сумма должна быть больше нуля")
    if minor > MAX_AMOUNT_MINOR:
        raise ParseError("Слишком большая сумма")
    sign = match.group(1)
    description = _clean_description(rest[: match.start()] + " " + rest[match.end():])
    if sign == "+":
        kind = INCOME
    elif sign:
        kind = EXPENSE
    elif _looks_like_income(description):
        kind = INCOME
    else:
        kind = EXPENSE
    return ParsedEntry(
        amount=minor,
        kind=kind,
        description=description,
        entry_date=entry_date or today,
        explicit_sign=bool(sign),
    )


def parse_time(text: str) -> Optional[str]:
    match = re.fullmatch(r"\s*(\d{1,2})[:.\- ](\d{2})\s*", text)
    if not match:
        return None
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return None
    return f"{hours:02d}:{minutes:02d}"


def parse_tz_offset(text: str) -> Optional[int]:
    cleaned = text.strip().lower().replace("utc", "").replace("gmt", "").replace("мск", "3")
    cleaned = cleaned.replace("−", "-").replace("–", "-").replace(" ", "")
    if not re.fullmatch(r"[+-]?\d{1,2}", cleaned):
        return None
    value = int(cleaned)
    if value < -12 or value > 14:
        return None
    return value
