from datetime import date

from bot.services.models import EXPENSE, INCOME, Entry
from bot.services.periods import (
    MONTH, TODAY, WEEK, comparison_period, format_range, local_today, period_for, period_title, relative_day,
)
from bot.services.summary import by_category, compare, group_by_day, running_balance, summarize
from datetime import datetime, timezone


def make(id_, kind, amount, category, day):
    return Entry(id=id_, kind=kind, amount=amount, category=category, description="", entry_date=day)


ENTRIES = [
    make(1, INCOME, 5000000, "Зарплата", date(2026, 10, 1)),
    make(2, EXPENSE, 35000, "Кафе", date(2026, 10, 2)),
    make(3, EXPENSE, 120000, "Продукты", date(2026, 10, 2)),
    make(4, EXPENSE, 45000, "Кафе", date(2026, 10, 3)),
    make(5, EXPENSE, 200000, "Транспорт", date(2026, 10, 5)),
]


def test_summarize_totals_and_top():
    summary = summarize(ENTRIES)
    assert summary.income == 5000000
    assert summary.expense == 400000
    assert summary.balance == 4600000
    assert summary.count == 5
    assert summary.top[0] == ("Транспорт", 200000, 0.5)
    assert summary.top[1] == ("Продукты", 120000, 0.3)
    assert summary.top[2] == ("Кафе", 80000, 0.2)


def test_summarize_empty():
    summary = summarize([])
    assert summary.income == 0 and summary.expense == 0 and summary.top == []


def test_by_category_sorted():
    assert by_category(ENTRIES, EXPENSE) == [("Транспорт", 200000), ("Продукты", 120000), ("Кафе", 80000)]
    assert by_category(ENTRIES, INCOME) == [("Зарплата", 5000000)]


def test_compare_periods():
    current = summarize(ENTRIES)
    previous = summarize([make(9, EXPENSE, 200000, "Кафе", date(2026, 9, 2))])
    result = compare(current, previous)
    assert result.expense_delta == 200000
    assert result.expense_pct == 100
    assert result.income_delta == 5000000
    assert result.income_pct is None


def test_group_by_day_fills_gaps():
    days = group_by_day(ENTRIES, date(2026, 10, 1), date(2026, 10, 5), EXPENSE)
    assert [amount for _, amount in days] == [0, 155000, 45000, 0, 200000]


def test_running_balance_with_opening():
    line = running_balance(ENTRIES, date(2026, 10, 1), date(2026, 10, 5), opening=100000)
    assert [amount for _, amount in line] == [5100000, 4945000, 4900000, 4900000, 4700000]


def test_period_for():
    today = date(2026, 10, 28)
    assert period_for(TODAY, today).start == today
    week = period_for(WEEK, today)
    assert week.start == date(2026, 10, 26) and week.end == date(2026, 11, 1)
    month = period_for(MONTH, today)
    assert month.start == date(2026, 10, 1) and month.end == date(2026, 10, 31)


def test_comparison_period_matches_elapsed_days():
    today = date(2026, 10, 28)
    assert comparison_period(period_for(TODAY, today), today).start == date(2026, 10, 27)
    week_prev = comparison_period(period_for(WEEK, today), today)
    assert week_prev.start == date(2026, 10, 19) and week_prev.end == date(2026, 10, 21)
    month_prev = comparison_period(period_for(MONTH, today), today)
    assert month_prev.start == date(2026, 9, 1) and month_prev.end == date(2026, 9, 28)
    march = comparison_period(period_for(MONTH, date(2026, 3, 31)), date(2026, 3, 31))
    assert march.end == date(2026, 2, 28)


def test_titles_and_labels():
    today = date(2026, 10, 28)
    assert period_title(period_for(TODAY, today), today) == "Сегодня, 28 октября"
    assert period_title(period_for(MONTH, today), today) == "Октябрь 2026"
    assert format_range(date(2026, 10, 26), date(2026, 11, 1)) == "26 октября – 1 ноября"
    assert relative_day(today, today) == "сегодня"
    assert relative_day(date(2026, 10, 27), today) == "вчера"
    assert relative_day(date(2026, 10, 15), today) == "15.10"


def test_local_today_uses_offset():
    moment = datetime(2026, 10, 28, 22, 30, tzinfo=timezone.utc)
    assert local_today(3, moment) == date(2026, 10, 29)
    assert local_today(-5, moment) == date(2026, 10, 28)
