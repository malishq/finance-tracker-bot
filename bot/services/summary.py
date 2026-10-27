from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from .models import EXPENSE, INCOME, Entry


@dataclass
class Summary:
    income: int = 0
    expense: int = 0
    count: int = 0
    top: List[Tuple[str, int, float]] = field(default_factory=list)

    @property
    def balance(self) -> int:
        return self.income - self.expense


@dataclass
class Comparison:
    expense_delta: int
    expense_pct: Optional[float]
    income_delta: int
    income_pct: Optional[float]


def by_category(entries: Iterable[Entry], kind: str = EXPENSE) -> List[Tuple[str, int]]:
    totals: Dict[str, int] = {}
    for entry in entries:
        if entry.kind != kind:
            continue
        totals[entry.category] = totals.get(entry.category, 0) + entry.amount
    return sorted(totals.items(), key=lambda item: (-item[1], item[0]))


def summarize(entries: Iterable[Entry], top_n: int = 5) -> Summary:
    entries = list(entries)
    summary = Summary(count=len(entries))
    for entry in entries:
        if entry.kind == INCOME:
            summary.income += entry.amount
        else:
            summary.expense += entry.amount
    if summary.expense:
        for category, amount in by_category(entries, EXPENSE)[:top_n]:
            summary.top.append((category, amount, amount / summary.expense))
    return summary


def _pct(current: int, previous: int) -> Optional[float]:
    if previous <= 0:
        return None
    return (current - previous) / previous * 100


def compare(current: Summary, previous: Summary) -> Comparison:
    return Comparison(
        expense_delta=current.expense - previous.expense,
        expense_pct=_pct(current.expense, previous.expense),
        income_delta=current.income - previous.income,
        income_pct=_pct(current.income, previous.income),
    )


def group_by_day(entries: Iterable[Entry], start: date, end: date, kind: str = EXPENSE) -> List[Tuple[date, int]]:
    totals: Dict[date, int] = {}
    for entry in entries:
        if entry.kind == kind and start <= entry.entry_date <= end:
            totals[entry.entry_date] = totals.get(entry.entry_date, 0) + entry.amount
    result = []
    current = start
    while current <= end:
        result.append((current, totals.get(current, 0)))
        current += timedelta(days=1)
    return result


def running_balance(entries: Iterable[Entry], start: date, end: date, opening: int = 0) -> List[Tuple[date, int]]:
    deltas: Dict[date, int] = {}
    for entry in entries:
        if start <= entry.entry_date <= end:
            signed = entry.amount if entry.kind == INCOME else -entry.amount
            deltas[entry.entry_date] = deltas.get(entry.entry_date, 0) + signed
    result = []
    total = opening
    current = start
    while current <= end:
        total += deltas.get(current, 0)
        result.append((current, total))
        current += timedelta(days=1)
    return result


def average_per_day(total: int, days: int) -> int:
    return round(total / days) if days > 0 else 0
