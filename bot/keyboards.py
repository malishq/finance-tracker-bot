from __future__ import annotations

from typing import Dict, Iterable, List, Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .services.categories import Category
from .services.models import EXPENSE, INCOME, Entry

MENU_TODAY = "📅 Сегодня"
MENU_WEEK = "📆 Неделя"
MENU_MONTH = "🗓 Месяц"
MENU_CHARTS = "📊 Графики"
MENU_HISTORY = "📝 Записи"
MENU_BUDGET = "🎯 Бюджет"
MENU_EXPORT = "📤 Экспорт"
MENU_SETTINGS = "⚙️ Настройки"
MENU_BUTTONS = [MENU_TODAY, MENU_WEEK, MENU_MONTH, MENU_CHARTS, MENU_HISTORY, MENU_BUDGET, MENU_EXPORT, MENU_SETTINGS]

CURRENCIES = ["₽", "$", "€", "₸", "₴", "¥", "£", "Br"]
TZ_PRESETS = [
    (2, "UTC+2 Калининград"), (3, "UTC+3 Москва"), (4, "UTC+4 Самара"), (5, "UTC+5 Екатеринбург"),
    (6, "UTC+6 Омск"), (7, "UTC+7 Новосибирск"), (8, "UTC+8 Иркутск"), (10, "UTC+10 Владивосток"),
]
REMINDER_PRESETS = ["09:00", "12:00", "20:00", "21:00", "22:00"]
EXPORT_PERIODS = [("month", "Этот месяц"), ("prev", "Прошлый месяц"), ("quarter", "3 месяца"), ("all", "Всё время")]
BACK = "← Назад"


class EntryCb(CallbackData, prefix="e"):
    action: str
    entry_id: int


class SetCatCb(CallbackData, prefix="sc"):
    entry_id: int
    slug: str
    src: str


class ChartCb(CallbackData, prefix="ch"):
    kind: str


class HistCb(CallbackData, prefix="h"):
    action: str
    value: int


class EditFieldCb(CallbackData, prefix="ef"):
    entry_id: int
    field: str


class BudgetCb(CallbackData, prefix="b", sep="|"):
    action: str
    slug: str = ""


class ExportCb(CallbackData, prefix="x"):
    period: str
    fmt: str = ""


class SettingsCb(CallbackData, prefix="s", sep="|"):
    action: str
    value: str = ""


class CategoryCb(CallbackData, prefix="c", sep="|"):
    action: str
    value: str = ""


class CancelCb(CallbackData, prefix="cancel"):
    pass


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=MENU_TODAY), KeyboardButton(text=MENU_WEEK), KeyboardButton(text=MENU_MONTH)],
        [KeyboardButton(text=MENU_CHARTS), KeyboardButton(text=MENU_HISTORY), KeyboardButton(text=MENU_BUDGET)],
        [KeyboardButton(text=MENU_EXPORT), KeyboardButton(text=MENU_SETTINGS)],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, input_field_placeholder="Например: 350 кофе")


def cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отмена", callback_data=CancelCb())
    return builder.as_markup()


def entry_actions(entry_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🏷 Изменить категорию", callback_data=EntryCb(action="cat", entry_id=entry_id))
    builder.button(text="🗑 Удалить", callback_data=EntryCb(action="del", entry_id=entry_id))
    builder.adjust(1, 1)
    return builder.as_markup()


def category_grid(categories: Sequence[Category], entry_id: int, src: str, back: CallbackData) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category.label, callback_data=SetCatCb(entry_id=entry_id, slug=category.slug, src=src))
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text=BACK, callback_data=back.pack()))
    return builder.as_markup()


def charts_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🥧 По категориям", callback_data=ChartCb(kind="pie"))
    builder.button(text="📊 По дням", callback_data=ChartCb(kind="days"))
    builder.button(text="📈 Баланс", callback_data=ChartCb(kind="balance"))
    builder.adjust(2, 1)
    return builder.as_markup()


def history_keyboard(entries: Sequence[Entry], offset: int, page_size: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, entry in enumerate(entries, start=1):
        builder.row(
            InlineKeyboardButton(text=f"✏️ {index}", callback_data=HistCb(action="edit", value=entry.id).pack()),
            InlineKeyboardButton(text=f"🗑 {index}", callback_data=HistCb(action="del", value=entry.id).pack()),
        )
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="← Новее", callback_data=HistCb(action="page", value=max(0, offset - page_size)).pack()))
    if offset + page_size < total:
        nav.append(InlineKeyboardButton(text="Старее →", callback_data=HistCb(action="page", value=offset + page_size).pack()))
    if nav:
        builder.row(*nav)
    return builder.as_markup()


def edit_fields(entry: Entry) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💵 Сумма", callback_data=EditFieldCb(entry_id=entry.id, field="amount"))
    builder.button(text="✏️ Описание", callback_data=EditFieldCb(entry_id=entry.id, field="desc"))
    builder.button(text="🏷 Категория", callback_data=EditFieldCb(entry_id=entry.id, field="cat"))
    builder.button(text="📅 Дата", callback_data=EditFieldCb(entry_id=entry.id, field="date"))
    toggle = "Сделать доходом" if entry.kind == EXPENSE else "Сделать расходом"
    builder.button(text=f"🔁 {toggle}", callback_data=EditFieldCb(entry_id=entry.id, field="kind"))
    builder.button(text=BACK, callback_data=HistCb(action="page", value=0))
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def confirm_delete(entry_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Да, удалить", callback_data=HistCb(action="confirm", value=entry_id))
    builder.button(text="Отмена", callback_data=HistCb(action="page", value=0))
    builder.adjust(2)
    return builder.as_markup()


def budget_menu(has_budgets: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Задать лимит", callback_data=BudgetCb(action="set"))
    if has_budgets:
        builder.button(text="🗑 Убрать лимит", callback_data=BudgetCb(action="del"))
    builder.adjust(2)
    return builder.as_markup()


def budget_categories(categories: Sequence[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category.label, callback_data=BudgetCb(action="pick", slug=category.slug))
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text=BACK, callback_data=BudgetCb(action="back").pack()))
    return builder.as_markup()


def budget_delete_list(names: Iterable[str], categories: Sequence[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    by_name: Dict[str, Category] = {c.name: c for c in categories}
    for name in names:
        category = by_name.get(name)
        label = category.label if category else name
        slug = category.slug if category else ""
        builder.button(text=f"🗑 {label}", callback_data=BudgetCb(action="rm", slug=slug or name.replace("|", " ")[:20]))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=BACK, callback_data=BudgetCb(action="back").pack()))
    return builder.as_markup()


def export_periods() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in EXPORT_PERIODS:
        builder.button(text=label, callback_data=ExportCb(period=code))
    builder.adjust(2)
    return builder.as_markup()


def export_formats(period: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 CSV", callback_data=ExportCb(period=period, fmt="csv"))
    builder.button(text="📗 Excel (XLSX)", callback_data=ExportCb(period=period, fmt="xlsx"))
    builder.button(text=BACK, callback_data=ExportCb(period="back"))
    builder.adjust(2, 1)
    return builder.as_markup()


def settings_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💱 Валюта", callback_data=SettingsCb(action="currency"))
    builder.button(text="🕒 Часовой пояс", callback_data=SettingsCb(action="tz"))
    builder.button(text="⏰ Напоминание", callback_data=SettingsCb(action="reminder"))
    builder.button(text="🗂 Категории", callback_data=SettingsCb(action="categories"))
    builder.adjust(2, 2)
    return builder.as_markup()


def currency_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code in CURRENCIES:
        builder.button(text=code, callback_data=SettingsCb(action="cur_set", value=code))
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="Другая…", callback_data=SettingsCb(action="cur_custom").pack()))
    builder.row(InlineKeyboardButton(text=BACK, callback_data=SettingsCb(action="menu").pack()))
    return builder.as_markup()


def tz_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for offset, label in TZ_PRESETS:
        builder.button(text=label, callback_data=SettingsCb(action="tz_set", value=str(offset)))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="Ввести вручную…", callback_data=SettingsCb(action="tz_custom").pack()))
    builder.row(InlineKeyboardButton(text=BACK, callback_data=SettingsCb(action="menu").pack()))
    return builder.as_markup()


def reminder_keyboard(enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for preset in REMINDER_PRESETS:
        builder.button(text=preset, callback_data=SettingsCb(action="rem_set", value=preset))
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text="Другое время…", callback_data=SettingsCb(action="rem_custom").pack()))
    if enabled:
        builder.row(InlineKeyboardButton(text="🔕 Выключить", callback_data=SettingsCb(action="rem_set", value="off").pack()))
    builder.row(InlineKeyboardButton(text=BACK, callback_data=SettingsCb(action="menu").pack()))
    return builder.as_markup()


def categories_menu(has_custom: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Для расходов", callback_data=CategoryCb(action="add", value=EXPENSE))
    builder.button(text="➕ Для доходов", callback_data=CategoryCb(action="add", value=INCOME))
    builder.adjust(2)
    if has_custom:
        builder.row(InlineKeyboardButton(text="🗑 Удалить свою", callback_data=CategoryCb(action="del_list").pack()))
    builder.row(InlineKeyboardButton(text="← К настройкам", callback_data=SettingsCb(action="menu").pack()))
    return builder.as_markup()


def custom_categories_delete(categories: Sequence[Category]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=f"🗑 {category.label}", callback_data=CategoryCb(action="rm", value=category.slug[1:]))
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text=BACK, callback_data=SettingsCb(action="categories").pack()))
    return builder.as_markup()
