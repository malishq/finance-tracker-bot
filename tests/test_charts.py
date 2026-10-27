from datetime import date, timedelta

from bot.services.charts import balance_line, bars_by_day, pie_by_category

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_pie_renders_png_and_folds_tail():
    data = [(f"Категория {i}", (10 - i) * 10000) for i in range(9)]
    image = pie_by_category(data, "Расходы по категориям", "Октябрь 2026", "₽")
    assert image[:8] == PNG_MAGIC
    assert pie_by_category([], "Расходы", "пусто", "₽")[:8] == PNG_MAGIC


def test_bars_and_line_render_png():
    start = date(2026, 9, 29)
    points = [(start + timedelta(days=i), (i % 7) * 25000) for i in range(30)]
    assert bars_by_day(points, "Расходы по дням", "30 дней", "₽")[:8] == PNG_MAGIC
    assert bars_by_day([(start, 0)], "Расходы по дням", "пусто", "₽")[:8] == PNG_MAGIC
    balance = [(start + timedelta(days=i), 100000 - i * 7000) for i in range(30)]
    assert balance_line(balance, "Баланс", "30 дней", "₽")[:8] == PNG_MAGIC
    assert balance_line([], "Баланс", "пусто", "₽")[:8] == PNG_MAGIC
