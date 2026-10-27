import io
from datetime import date

from openpyxl import load_workbook

from bot.services.export import entries_to_csv, entries_to_xlsx, export_filename
from bot.services.models import EXPENSE, INCOME, Entry

ENTRIES = [
    Entry(2, EXPENSE, 35050, "Кафе", "кофе", date(2026, 10, 2)),
    Entry(1, INCOME, 5000000, "Зарплата", "зарплата", date(2026, 10, 1)),
]


def test_csv_has_bom_header_and_rows():
    data = entries_to_csv(ENTRIES)
    text = data.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("\ufeff").strip().splitlines()
    assert lines[0] == "Дата;Тип;Категория;Описание;Сумма"
    assert lines[1] == "01.10.2026;Доход;Зарплата;зарплата;50000,00"
    assert lines[2] == "02.10.2026;Расход;Кафе;кофе;-350,50"


def test_xlsx_rows_and_totals():
    workbook = load_workbook(io.BytesIO(entries_to_xlsx(ENTRIES, "₽")))
    sheet = workbook.active
    assert sheet["A1"].value == "Дата"
    assert sheet["A2"].value.date() == date(2026, 10, 1)
    assert sheet["E2"].value == 50000
    assert sheet["E3"].value == -350.5
    assert sheet["D5"].value == "Доходы" and sheet["E5"].value == 50000
    assert sheet["D6"].value == "Расходы" and sheet["E6"].value == 350.5
    assert sheet["D7"].value == "Баланс" and sheet["E7"].value == 49649.5


def test_export_filename():
    assert export_filename(date(2026, 10, 1), date(2026, 10, 31), "csv") == "finance_2026-10.csv"
    assert export_filename(date(2026, 8, 1), date(2026, 10, 31), "xlsx") == "finance_2026-08-01_2026-10-31.xlsx"
