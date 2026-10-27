from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..db import Database
from ..keyboards import (
    MENU_SETTINGS, CategoryCb, SettingsCb, cancel_keyboard, categories_menu, currency_keyboard,
    custom_categories_delete, main_menu, reminder_keyboard, settings_menu, tz_keyboard,
)
from ..services.categories import find_by_name
from ..services.models import EXPENSE, INCOME
from ..services.parser import parse_time, parse_tz_offset
from ..services.periods import local_now
from ..states import CategoryForm, SettingsForm
from ..utils import UserContext, esc, load_context, plain_text, respond

router = Router(name="settings")

DEFAULT_EMOJI = "🏷"
MAX_NAME = 30


def tz_label(offset: int) -> str:
    sign = "+" if offset >= 0 else "−"
    return f"UTC{sign}{abs(offset)}"


def settings_text(ctx: UserContext) -> str:
    reminder = ctx.settings.reminder_time or "выключено"
    now = local_now(ctx.settings.tz_offset).strftime("%H:%M")
    return (
        "<b>Настройки</b>\n\n"
        f"Валюта: {esc(ctx.currency)}\n"
        f"Часовой пояс: {tz_label(ctx.settings.tz_offset)} (сейчас {now})\n"
        f"Напоминание: {reminder}\n"
        f"Своих категорий: {len(ctx.custom)}"
    )


def categories_text(ctx: UserContext) -> str:
    expense = ", ".join(c.label for c in ctx.categories(EXPENSE) if not c.custom)
    income = ", ".join(c.label for c in ctx.categories(INCOME) if not c.custom)
    lines = ["<b>Категории</b>", "", f"Расходы: {expense}", "", f"Доходы: {income}", ""]
    if ctx.custom:
        own = ", ".join(f"{esc(c.label)} ({'доход' if c.kind == INCOME else 'расход'})" for c in ctx.custom)
        lines.append(f"Свои: {own}")
    else:
        lines.append("Своих категорий пока нет. Добавь, если не хватает стандартных.")
    return "\n".join(lines)


@router.message(Command("settings"))
@router.message(F.text == MENU_SETTINGS)
async def cmd_settings(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, message.from_user.id)
    await message.answer(settings_text(ctx), reply_markup=settings_menu())


@router.callback_query(SettingsCb.filter(F.action == "menu"))
async def menu(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, settings_text(ctx), settings_menu())
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "currency"))
async def currency(callback: CallbackQuery) -> None:
    await respond(callback, "Выбери валюту:", currency_keyboard())
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "cur_set"))
async def currency_set(callback: CallbackQuery, callback_data: SettingsCb, db: Database) -> None:
    await db.update_user(callback.from_user.id, currency=callback_data.value)
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, settings_text(ctx), settings_menu())
    await callback.answer(f"Валюта: {callback_data.value}")


@router.callback_query(SettingsCb.filter(F.action == "cur_custom"))
async def currency_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsForm.waiting_currency)
    await respond(callback, "Напиши символ или код валюты, например <code>₸</code> или <code>USD</code>:", cancel_keyboard())
    await callback.answer()


@router.message(SettingsForm.waiting_currency, plain_text())
async def currency_save(message: Message, db: Database, state: FSMContext) -> None:
    value = message.text.strip()
    if not value or len(value) > 5:
        await message.answer("До 5 символов, например <code>₸</code> или <code>USD</code>.", reply_markup=cancel_keyboard())
        return
    await state.clear()
    await db.update_user(message.from_user.id, currency=value)
    ctx = await load_context(db, message.from_user.id)
    await message.answer(f"✅ Валюта: {esc(value)}", reply_markup=main_menu())
    await message.answer(settings_text(ctx), reply_markup=settings_menu())


@router.callback_query(SettingsCb.filter(F.action == "tz"))
async def tz(callback: CallbackQuery, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, f"Сейчас {tz_label(ctx.settings.tz_offset)}. Выбери часовой пояс:", tz_keyboard())
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "tz_set"))
async def tz_set(callback: CallbackQuery, callback_data: SettingsCb, db: Database) -> None:
    offset = parse_tz_offset(callback_data.value)
    if offset is None:
        await callback.answer("Не понял смещение", show_alert=True)
        return
    await db.update_user(callback.from_user.id, tz_offset=offset)
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, settings_text(ctx), settings_menu())
    await callback.answer(f"Часовой пояс: {tz_label(offset)}")


@router.callback_query(SettingsCb.filter(F.action == "tz_custom"))
async def tz_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsForm.waiting_tz)
    await respond(callback, "Напиши смещение от UTC, например <code>+3</code> или <code>-5</code>:", cancel_keyboard())
    await callback.answer()


@router.message(SettingsForm.waiting_tz, plain_text())
async def tz_save(message: Message, db: Database, state: FSMContext) -> None:
    offset = parse_tz_offset(message.text)
    if offset is None:
        await message.answer("Не понял. Напиши число от −12 до +14, например <code>+3</code>.", reply_markup=cancel_keyboard())
        return
    await state.clear()
    await db.update_user(message.from_user.id, tz_offset=offset)
    ctx = await load_context(db, message.from_user.id)
    await message.answer(f"✅ Часовой пояс: {tz_label(offset)}", reply_markup=main_menu())
    await message.answer(settings_text(ctx), reply_markup=settings_menu())


@router.callback_query(SettingsCb.filter(F.action == "reminder"))
async def reminder(callback: CallbackQuery, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    current = ctx.settings.reminder_time or "выключено"
    await respond(
        callback,
        f"Напоминание «запиши траты» сейчас: <b>{current}</b>.\nВыбери время по своему часовому поясу:",
        reminder_keyboard(bool(ctx.settings.reminder_time)),
    )
    await callback.answer()


@router.callback_query(SettingsCb.filter(F.action == "rem_set"))
async def reminder_set(callback: CallbackQuery, callback_data: SettingsCb, db: Database) -> None:
    if callback_data.value == "off":
        await db.update_user(callback.from_user.id, reminder_time=None)
        answer = "Напоминание выключено"
    else:
        value = parse_time(callback_data.value)
        if value is None:
            await callback.answer("Не понял время", show_alert=True)
            return
        await db.update_user(callback.from_user.id, reminder_time=value, last_reminder_date=None)
        answer = f"Напомню в {value}"
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, settings_text(ctx), settings_menu())
    await callback.answer(answer)


@router.callback_query(SettingsCb.filter(F.action == "rem_custom"))
async def reminder_custom(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SettingsForm.waiting_reminder)
    await respond(callback, "Во сколько напоминать? Напиши время, например <code>21:30</code>:", cancel_keyboard())
    await callback.answer()


@router.message(SettingsForm.waiting_reminder, plain_text())
async def reminder_save(message: Message, db: Database, state: FSMContext) -> None:
    value = parse_time(message.text)
    if value is None:
        await message.answer("Не понял время. Формат ЧЧ:ММ, например <code>21:30</code>.", reply_markup=cancel_keyboard())
        return
    await state.clear()
    await db.update_user(message.from_user.id, reminder_time=value, last_reminder_date=None)
    ctx = await load_context(db, message.from_user.id)
    await message.answer(f"✅ Буду напоминать в {value}", reply_markup=main_menu())
    await message.answer(settings_text(ctx), reply_markup=settings_menu())


@router.callback_query(SettingsCb.filter(F.action == "categories"))
async def categories(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, categories_text(ctx), categories_menu(bool(ctx.custom)))
    await callback.answer()


@router.callback_query(CategoryCb.filter(F.action == "add"))
async def category_add(callback: CallbackQuery, callback_data: CategoryCb, state: FSMContext) -> None:
    kind = INCOME if callback_data.value == INCOME else EXPENSE
    await state.set_state(CategoryForm.waiting_name)
    await state.update_data(kind=kind)
    word = "доходов" if kind == INCOME else "расходов"
    await respond(
        callback,
        f"Как назвать категорию {word}? Можно с эмодзи в начале, например <code>🎮 Игры</code>:",
        cancel_keyboard(),
    )
    await callback.answer()


@router.message(CategoryForm.waiting_name, plain_text())
async def category_save(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    kind = data.get("kind", EXPENSE)
    parts = message.text.strip().split(maxsplit=1)
    if len(parts) == 2 and not any(ch.isalnum() for ch in parts[0]):
        emoji, name = parts[0], parts[1].strip()
    else:
        emoji, name = DEFAULT_EMOJI, message.text.strip()
    if not name or len(name) > MAX_NAME:
        await message.answer(f"Название от 1 до {MAX_NAME} символов. Попробуй ещё раз:", reply_markup=cancel_keyboard())
        return
    ctx = await load_context(db, message.from_user.id)
    if find_by_name(name, kind, ctx.custom) is not None:
        await message.answer("Такая категория уже есть. Напиши другое название:", reply_markup=cancel_keyboard())
        return
    created = await db.add_category(message.from_user.id, kind, name, emoji)
    await state.clear()
    if created is None:
        await message.answer("Такая категория уже есть.", reply_markup=main_menu())
        return
    word = "доход" if kind == INCOME else "расход"
    await message.answer(f"✅ Добавил категорию {esc(created.label)} ({word})", reply_markup=main_menu())
    ctx = await load_context(db, message.from_user.id)
    await message.answer(categories_text(ctx), reply_markup=categories_menu(True))


@router.callback_query(CategoryCb.filter(F.action == "del_list"))
async def category_delete_list(callback: CallbackQuery, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    if not ctx.custom:
        await callback.answer("Своих категорий нет", show_alert=True)
        return
    await respond(callback, "Какую категорию удалить? Записи с ней останутся.", custom_categories_delete(ctx.custom))
    await callback.answer()


@router.callback_query(CategoryCb.filter(F.action == "rm"))
async def category_remove(callback: CallbackQuery, callback_data: CategoryCb, db: Database) -> None:
    removed = False
    if callback_data.value.isdigit():
        removed = await db.delete_category(callback.from_user.id, int(callback_data.value))
    ctx = await load_context(db, callback.from_user.id)
    await respond(callback, categories_text(ctx), categories_menu(bool(ctx.custom)))
    await callback.answer("Удалено" if removed else "Категория не найдена")
