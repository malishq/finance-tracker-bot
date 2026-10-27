from bot.services.budgets import EXCEEDED, OK, WARNING, alert_text, budget_status, crossed_threshold, progress_bar, statuses_from
from bot.services.money import fmt_money, fmt_percent


def test_levels():
    assert budget_status("Кафе", 1000000, 300000).level == OK
    assert budget_status("Кафе", 1000000, 800000).level == WARNING
    assert budget_status("Кафе", 1000000, 1000000).level == WARNING
    assert budget_status("Кафе", 1000000, 1000100).level == EXCEEDED


def test_alert_texts():
    assert alert_text(budget_status("Кафе", 1000000, 300000), "₽") is None
    warning = alert_text(budget_status("Кафе", 1000000, 850000), "₽")
    assert "85%" in warning and "1 500 ₽" in warning
    exceeded = alert_text(budget_status("Кафе", 1000000, 1200000), "₽")
    assert "превышен" in exceeded and "2 000 ₽" in exceeded


def test_crossed_threshold_only_on_change():
    before = budget_status("Кафе", 1000000, 700000)
    after = budget_status("Кафе", 1000000, 850000)
    assert crossed_threshold(before, after)
    assert not crossed_threshold(after, budget_status("Кафе", 1000000, 900000))
    assert crossed_threshold(after, budget_status("Кафе", 1000000, 1100000))


def test_progress_bar_and_sorting():
    assert progress_bar(0.5) == "▓▓▓▓▓░░░░░"
    assert progress_bar(1.7) == "▓▓▓▓▓▓▓▓▓▓"
    statuses = statuses_from({"Кафе": 1000, "Такси": 1000}, {"Кафе": 100, "Такси": 900})
    assert [s.category for s in statuses] == ["Такси", "Кафе"]


def test_money_format():
    assert fmt_money(123456789, "₽") == "1 234 567,89 ₽"
    assert fmt_money(35000, "₽") == "350 ₽"
    assert fmt_money(-35000, "₽") == "−350 ₽"
    assert fmt_money(35000, "₽", signed=True) == "+350 ₽"
    assert fmt_money(0, "$") == "0 $"
    assert fmt_percent(0.345) == "35%"
