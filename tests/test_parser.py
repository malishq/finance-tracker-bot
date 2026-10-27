from datetime import date

import pytest

from bot.services.models import EXPENSE, INCOME
from bot.services.parser import ParseError, parse_amount, parse_entry, parse_time, parse_tz_offset

TODAY = date(2026, 10, 28)


@pytest.mark.parametrize(
    "text, amount, kind, description, entry_date",
    [
        ("-350 кофе", 35000, EXPENSE, "кофе", TODAY),
        ("+50000 зарплата", 5000000, INCOME, "зарплата", TODAY),
        ("1200 продукты", 120000, EXPENSE, "продукты", TODAY),
        ("350 кофе вчера", 35000, EXPENSE, "кофе", date(2026, 10, 27)),
        ("1 200,50 продукты", 120050, EXPENSE, "продукты", TODAY),
        ("+50 000 аванс", 5000000, INCOME, "аванс", TODAY),
        ("−99.9 метро", 9990, EXPENSE, "метро", TODAY),
        ("кофе 350", 35000, EXPENSE, "кофе", TODAY),
        ("2к такси", 200000, EXPENSE, "такси", TODAY),
        ("1.5к подарок маме 15.10", 150000, EXPENSE, "подарок маме", date(2026, 10, 15)),
        ("450р обед", 45000, EXPENSE, "обед", TODAY),
        ("450 руб. обед позавчера", 45000, EXPENSE, "обед", date(2026, 10, 26)),
        ("12000 аренда 01.11", 1200000, EXPENSE, "аренда", date(2025, 11, 1)),
        ("3000 стоматолог 05.03.2026", 300000, EXPENSE, "стоматолог", date(2026, 3, 5)),
        ("Зарплата 80000", 8000000, INCOME, "Зарплата", TODAY),
        ("500", 50000, EXPENSE, "", TODAY),
        ("1 000 000 продажа машины", 100000000, EXPENSE, "продажа машины", TODAY),
        ("11.10 300 кино", 30000, EXPENSE, "кино", date(2026, 10, 11)),
    ],
)
def test_parse_entry(text, amount, kind, description, entry_date):
    parsed = parse_entry(text, today=TODAY)
    assert parsed.amount == amount
    assert parsed.kind == kind
    assert parsed.description == description
    assert parsed.entry_date == entry_date


def test_explicit_sign_flag():
    assert parse_entry("-350 кофе", today=TODAY).explicit_sign is True
    assert parse_entry("350 кофе", today=TODAY).explicit_sign is False


def test_explicit_minus_beats_income_words():
    parsed = parse_entry("-5000 премия коллеге", today=TODAY)
    assert parsed.kind == EXPENSE


@pytest.mark.parametrize("text", ["кофе", "", "   ", "0 кофе", "-0,00 кофе", "привет, как дела?"])
def test_parse_entry_errors(text):
    with pytest.raises(ParseError):
        parse_entry(text, today=TODAY)


def test_too_big_amount():
    with pytest.raises(ParseError):
        parse_entry("99999999999 что-то", today=TODAY)


def test_parse_amount_only():
    assert parse_amount("15 000") == 1500000
    assert parse_amount("15000 руб") == 1500000
    assert parse_amount("7,5к") == 750000
    with pytest.raises(ParseError):
        parse_amount("много")


def test_parse_time():
    assert parse_time("21:00") == "21:00"
    assert parse_time("9.05") == "09:05"
    assert parse_time("24:00") is None
    assert parse_time("вечером") is None


def test_parse_tz_offset():
    assert parse_tz_offset("+3") == 3
    assert parse_tz_offset("UTC-5") == -5
    assert parse_tz_offset("7") == 7
    assert parse_tz_offset("+15") is None
    assert parse_tz_offset("Москва") is None
