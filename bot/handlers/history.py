from __future__ import annotations

from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from ..db import Database
from ..keyboards import (
    MENU_HISTORY, EditFieldCb, HistCb, SetCatCb, cancel_keyboard, category_grid, confirm_delete, edit_fields,
    history_keyboard,
)
from ..services.categorizer import guess_category, rule_keyword
from ..services.models import EXPENSE, INCOME
from ..services.parser import ParseError, parse_amount, parse_date
from ..states import EditEntry
from ..texts import NO_ENTRIES
from ..utils import UserContext, entry_line, esc, load_context, plain_text, respond

router = Router(name="history")

PAGE_SIZE = 8
PROMPTS = {
    "amount": "Введи новую сумму, например <code>450</code> или <code>1 200,50</code>:",
    "desc": "Введи новое описание:",
    "date": "Введи дату: <code>сегодня</code>, <code>вчера</code> или <code>дд.мм</code>:",
}


async def history_view(db: Database, ctx: UserContext, offset: int) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    total = await db.count_entries(ctx.user_id)
    if total == 0:
        return NO_ENTRIES, None
    if offset >= total:
        offset = max(0, total - PAGE_SIZE)
    entries = await db.recent_entries(ctx.user_id, PAGE_SIZE, offset)
    lines = [f"<b>Последние записи</b> · {offset + 1}–{offset + len(entries)} из {total}", ""]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {entry_line(entry, ctx)}")
    lines.extend(["", "✏️ — изменить, 🗑 — удалить"])
    return "\n".join(lines), history_keyboard(entries, offset, PAGE_SIZE, total)


@router.message(Command("list"))
@router.message(F.text == MENU_HISTORY)
async def cmd_list(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, message.from_user.id)
    text, markup = await history_view(db, ctx, 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(HistCb.filter(F.action == "page"))
async def page(callback: CallbackQuery, callback_data: HistCb, db: Database, state: FSMContext) -> None:
    await state.clear()
    ctx = await load_context(db, callback.from_user.id)
    text, markup = await history_view(db, ctx, callback_data.value)
    await respond(callback, text, markup)
    await callback.answer()


@router.callback_query(HistCb.filter(F.action == "del"))
async def ask_delete(callback: CallbackQuery, callback_data: HistCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.value)
    if entry is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    await respond(callback, f"Удалить запись?\n{entry_line(entry, ctx)}", confirm_delete(entry.id))
    await callback.answer()


@router.callback_query(HistCb.filter(F.action == "confirm"))
async def confirm(callback: CallbackQuery, callback_data: HistCb, db: Database) -> None:
    user_id = callback.from_user.id
    deleted = await db.delete_entry(user_id, callback_data.value)
    ctx = await load_context(db, user_id)
    text, markup = await history_view(db, ctx, 0)
    await respond(callback, text, markup)
    await callback.answer("Удалено" if deleted else "Запись уже удалена")


@router.callback_query(HistCb.filter(F.action == "edit"))
async def ask_edit(callback: CallbackQuery, callback_data: HistCb, db: Database, state: FSMContext) -> None:
    await state.clear()
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.value)
    if entry is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    await respond(callback, f"Что изменить?\n{entry_line(entry, ctx)}", edit_fields(entry))
    await callback.answer()


@router.callback_query(EditFieldCb.filter())
async def edit_field(callback: CallbackQuery, callback_data: EditFieldCb, db: Database, state: FSMContext) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    field = callback_data.field
    if field == "kind":
        new_kind = INCOME if entry.kind == EXPENSE else EXPENSE
        rules = await db.rules(user_id)
        new_category = guess_category(entry.description, new_kind, rules)
        await db.update_entry(user_id, entry.id, kind=new_kind, category=new_category)
        entry.kind, entry.category = new_kind, new_category
        word = "доход" if new_kind == INCOME else "расход"
        await respond(callback, f"✅ Теперь это {word}:\n{entry_line(entry, ctx)}", edit_fields(entry))
        await callback.answer()
        return
    if field == "cat":
        await respond(
            callback,
            f"Выбери категорию:\n{entry_line(entry, ctx)}",
            category_grid(ctx.categories(entry.kind), entry.id, "hist", HistCb(action="edit", value=entry.id)),
        )
        await callback.answer()
        return
    await state.set_state(EditEntry.waiting_value)
    await state.update_data(entry_id=entry.id, field=field)
    await respond(callback, f"{entry_line(entry, ctx)}\n\n{PROMPTS[field]}", cancel_keyboard())
    await callback.answer()


@router.callback_query(SetCatCb.filter(F.src == "hist"))
async def set_category(callback: CallbackQuery, callback_data: SetCatCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    category = ctx.category_by_slug(callback_data.slug)
    if category is None or category.kind != entry.kind:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    await db.update_entry(user_id, entry.id, category=category.name)
    await db.set_rule(user_id, rule_keyword(entry.description), category.name)
    entry.category = category.name
    await respond(callback, f"✅ Категория изменена:\n{entry_line(entry, ctx)}", edit_fields(entry))
    await callback.answer()


@router.message(EditEntry.waiting_value, plain_text())
async def edit_value(message: Message, db: Database, state: FSMContext) -> None:
    user_id = message.from_user.id
    data = await state.get_data()
    entry = await db.get_entry(user_id, int(data.get("entry_id", 0)))
    if entry is None:
        await state.clear()
        await message.answer("Запись не найдена, возможно она уже удалена.")
        return
    ctx = await load_context(db, user_id)
    field = data.get("field")
    text = message.text.strip()
    if field == "amount":
        try:
            await db.update_entry(user_id, entry.id, amount=parse_amount(text))
        except ParseError as error:
            await message.answer(f"{error}. Попробуй ещё раз или нажми «Отмена».", reply_markup=cancel_keyboard())
            return
    elif field == "desc":
        await db.update_entry(user_id, entry.id, description=text[:120])
    elif field == "date":
        new_date = parse_date(text, ctx.today)
        if new_date is None:
            await message.answer(
                "Не понял дату. Напиши <code>сегодня</code>, <code>вчера</code> или <code>дд.мм</code>.",
                reply_markup=cancel_keyboard(),
            )
            return
        await db.update_entry(user_id, entry.id, entry_date=new_date)
    await state.clear()
    updated = await db.get_entry(user_id, entry.id)
    await message.answer(f"✅ Обновил:\n{entry_line(updated, ctx)}", reply_markup=edit_fields(updated))
