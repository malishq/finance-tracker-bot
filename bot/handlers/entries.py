from __future__ import annotations

import re
from typing import List, Optional

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.types import CallbackQuery, Message

from ..db import Database
from ..keyboards import EntryCb, SetCatCb, category_grid, entry_actions
from ..services.budgets import EXCEEDED, OK, alert_text, budget_status, crossed_threshold
from ..services.categories import FALLBACK, find_by_name
from ..services.categorizer import guess_category, rule_keyword
from ..services.models import EXPENSE, INCOME, Entry
from ..services.money import fmt_money
from ..services.parser import ParseError, parse_entry
from ..services.periods import MONTH, period_for, relative_day
from ..texts import NO_ENTRIES, PARSE_HINT
from ..utils import UserContext, entry_line, esc, load_context, plain_text, respond

router = Router(name="entries")

UNDO_RE = re.compile(r"^(отмени(ть)?|отмена|undo)(\s+последн\w*)?(\s+запись)?\s*$", re.IGNORECASE)
MAX_LINES = 20


async def budget_alert(db: Database, ctx: UserContext, entry: Entry) -> Optional[str]:
    if entry.kind != EXPENSE:
        return None
    limits = await db.budgets(ctx.user_id)
    limit = limits.get(entry.category)
    if not limit:
        return None
    month = period_for(MONTH, ctx.today)
    if not (month.start <= entry.entry_date <= month.end):
        return None
    spent = (await db.spent_by_category(ctx.user_id, month.start, month.end)).get(entry.category, 0)
    after = budget_status(entry.category, limit, spent)
    before = budget_status(entry.category, limit, max(0, spent - entry.amount))
    if after.level == OK:
        return None
    if crossed_threshold(before, after) or after.level == EXCEEDED:
        return alert_text(after, ctx.currency)
    return None


async def confirmation_text(db: Database, ctx: UserContext, entry: Entry, note: Optional[str] = None) -> str:
    kind_word = "доход" if entry.kind == INCOME else "расход"
    description = esc(entry.description) if entry.description else "без описания"
    lines = [
        f"✅ Записал {kind_word}: <b>{fmt_money(entry.amount, ctx.currency)}</b> · {ctx.label(entry.category, entry.kind)}",
        f"{description} · {relative_day(entry.entry_date, ctx.today)}",
    ]
    if note:
        lines.append(note)
    alert = await budget_alert(db, ctx, entry)
    if alert:
        lines.extend(["", alert])
    return "\n".join(lines)


@router.message(Command("undo"))
@router.message(StateFilter(None), F.text.regexp(UNDO_RE))
async def undo_last(message: Message, db: Database) -> None:
    user_id = message.from_user.id
    entry = await db.last_entry(user_id)
    if entry is None:
        await message.answer(NO_ENTRIES)
        return
    ctx = await load_context(db, user_id)
    await db.delete_entry(user_id, entry.id)
    await message.answer(f"↩️ Отменил последнюю запись:\n{entry_line(entry, ctx)}")


@router.message(StateFilter(None), F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer("Не знаю такой команды. Список команд — /help")


@router.message(StateFilter(None), plain_text())
async def add_entries(message: Message, db: Database) -> None:
    user_id = message.from_user.id
    ctx = await load_context(db, user_id)
    rules = await db.rules(user_id)
    lines = [line.strip() for line in message.text.splitlines() if line.strip()]
    failed: List[str] = []
    saved = 0
    for line in lines[:MAX_LINES]:
        try:
            parsed = parse_entry(line, ctx.today)
        except ParseError:
            failed.append(line)
            continue
        category = guess_category(parsed.description, parsed.kind, rules)
        if find_by_name(category, parsed.kind, ctx.custom) is None:
            category = FALLBACK[parsed.kind]
        entry_id = await db.add_entry(
            user_id, parsed.kind, parsed.amount, category, parsed.description, parsed.entry_date
        )
        entry = Entry(entry_id, parsed.kind, parsed.amount, category, parsed.description, parsed.entry_date)
        await message.answer(await confirmation_text(db, ctx, entry), reply_markup=entry_actions(entry_id))
        saved += 1
    if failed and saved == 0:
        await message.answer(PARSE_HINT)
    elif failed:
        await message.answer("Не понял строки:\n" + "\n".join(f"• {esc(line)}" for line in failed))


@router.callback_query(EntryCb.filter(F.action == "cat"))
async def choose_category(callback: CallbackQuery, callback_data: EntryCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Эта запись уже удалена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    subject = esc(entry.description) if entry.description else "этой записи"
    await respond(
        callback,
        f"Выбери категорию для «{subject}»:",
        category_grid(ctx.categories(entry.kind), entry.id, "new", EntryCb(action="back", entry_id=entry.id)),
    )
    await callback.answer()


@router.callback_query(EntryCb.filter(F.action == "back"))
async def back_to_entry(callback: CallbackQuery, callback_data: EntryCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Эта запись уже удалена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    await respond(callback, await confirmation_text(db, ctx, entry), entry_actions(entry.id))
    await callback.answer()


@router.callback_query(SetCatCb.filter(F.src == "new"))
async def set_category(callback: CallbackQuery, callback_data: SetCatCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Эта запись уже удалена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    category = ctx.category_by_slug(callback_data.slug)
    if category is None or category.kind != entry.kind:
        await callback.answer("Категория не найдена", show_alert=True)
        return
    await db.update_entry(user_id, entry.id, category=category.name)
    entry.category = category.name
    note = None
    keyword = rule_keyword(entry.description)
    if keyword:
        await db.set_rule(user_id, keyword, category.name)
        note = f"Запомнил: «{esc(entry.description)}» → {category.label}"
    await respond(callback, await confirmation_text(db, ctx, entry, note), entry_actions(entry.id))
    await callback.answer("Категория изменена")


@router.callback_query(EntryCb.filter(F.action == "del"))
async def delete_entry(callback: CallbackQuery, callback_data: EntryCb, db: Database) -> None:
    user_id = callback.from_user.id
    entry = await db.get_entry(user_id, callback_data.entry_id)
    if entry is None:
        await callback.answer("Эта запись уже удалена", show_alert=True)
        return
    ctx = await load_context(db, user_id)
    await db.delete_entry(user_id, entry.id)
    await respond(callback, f"🗑 Удалил запись:\n{entry_line(entry, ctx)}")
    await callback.answer()


@router.message(StateFilter(None))
async def unsupported(message: Message) -> None:
    await message.answer("Я понимаю только текст. Напиши, например: <code>350 кофе</code>")
