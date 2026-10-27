import pytest

from bot.services.categories import DEFAULT_CATEGORIES, categories_for, find_by_slug, label_for
from bot.services.categorizer import guess_category, normalize, rule_keyword
from bot.services.models import EXPENSE, INCOME


@pytest.mark.parametrize(
    "description, expected",
    [
        ("кофе", "Кафе"),
        ("кофе с собой", "Кафе"),
        ("метро", "Транспорт"),
        ("Такси домой", "Транспорт"),
        ("аптека", "Здоровье"),
        ("продукты пятёрочка", "Продукты"),
        ("Яндекс Такси", "Транспорт"),
        ("парковка", "Транспорт"),
        ("парк аттракционов", "Развлечения"),
        ("билет в кино", "Развлечения"),
        ("билеты на самолёт", "Путешествия"),
        ("кроссовки", "Одежда"),
        ("подарок маме", "Подарки"),
        ("корм коту", "Питомцы"),
        ("виноград", "Продукты"),
        ("вино", "Кафе"),
        ("непонятная трата", "Другое"),
        ("", "Другое"),
    ],
)
def test_expense_categories(description, expected):
    assert guess_category(description, EXPENSE) == expected


@pytest.mark.parametrize(
    "description, expected",
    [
        ("зарплата", "Зарплата"),
        ("аванс за октябрь", "Зарплата"),
        ("заказ на kwork", "Фриланс"),
        ("кэшбэк", "Кэшбэк и бонусы"),
        ("перевод от мамы", "Переводы и подарки"),
        ("дивиденды", "Инвестиции"),
        ("продал велосипед", "Продажи"),
        ("вернули долг", "Возвраты"),
        ("что-то", "Прочее"),
    ],
)
def test_income_categories(description, expected):
    assert guess_category(description, INCOME) == expected


def test_user_rules_have_priority():
    rules = {"кофе": "Продукты", "кофе с собой": "Развлечения"}
    assert guess_category("кофе", EXPENSE, rules) == "Продукты"
    assert guess_category("кофе с собой", EXPENSE, rules) == "Развлечения"
    assert guess_category("метро", EXPENSE, rules) == "Транспорт"


def test_normalize_and_rule_keyword():
    assert normalize("  Кофе, с Собой! ") == "кофе с собой"
    assert rule_keyword("Ёлка") == "елка"


def test_categories_for_puts_fallback_last():
    names = [c.name for c in categories_for(EXPENSE)]
    assert names[-1] == "Другое"
    assert "Кафе" in names
    income_names = [c.name for c in categories_for(INCOME)]
    assert income_names[-1] == "Прочее"


def test_slugs_are_unique():
    slugs = [c.slug for c in DEFAULT_CATEGORIES]
    assert len(slugs) == len(set(slugs))
    assert find_by_slug("cafe").name == "Кафе"
    assert find_by_slug("missing") is None


def test_label_for_unknown_category():
    assert label_for("Кафе", EXPENSE) == "☕ Кафе"
    assert label_for("Неизвестно", EXPENSE) == "📁 Неизвестно"
