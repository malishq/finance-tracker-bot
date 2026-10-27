from __future__ import annotations

import asyncio
from datetime import date
from typing import Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ..db import Database
from ..keyboards import EXPORT_PERIODS, MENU_EXPORT, ExportCb, export_formats, export_periods
from ..services.export import entries_to_csv, entries_to_xlsx, export_filename
from ..services.periods import format_range, month_bounds, shift_month
from ..utils import chat_id_of, load_context, respond

router = Router(name="export")

PERIOD_LABELS = dict(EXPORT_PERIODS)
PROMPT = "За какой период выгрузить записи?"


def resolve_period(code: str, today: date) -> Tuple[date, date]:
    if code == "prev":
        year, month = shift_month(today.year, today.month, -1)
        return month_bounds(year, month)
    if code == "quarter":
        year, month = shift_month(today.year, today.month, -2)
        return month_bounds(year, month)[0], month_bounds(today.year, today.month)[1]
    if code == "all":
        return date(2000, 1, 1), today
    return month_bounds(today.year, today.month)


@router.message(Command("export"))
@router.message(F.text == MENU_EXPORT)
async def cmd_export(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(PROMPT, reply_markup=export_periods())


@router.callback_query(ExportCb.filter(F.period == "back"))
async def back(callback: CallbackQuery) -> None:
    await respond(callback, PROMPT, export_periods())
    await callback.answer()


@router.callback_query(ExportCb.filter(F.fmt == ""))
async def choose_format(callback: CallbackQuery, callback_data: ExportCb) -> None:
    label = PERIOD_LABELS.get(callback_data.period, callback_data.period)
    await respond(callback, f"Период: <b>{label}</b>. В каком формате?", export_formats(callback_data.period))
    await callback.answer()


@router.callback_query(ExportCb.filter(F.fmt.in_({"csv", "xlsx"})))
async def send_export(callback: CallbackQuery, callback_data: ExportCb, db: Database) -> None:
    ctx = await load_context(db, callback.from_user.id)
    start, end = resolve_period(callback_data.period, ctx.today)
    entries = await db.entries_between(ctx.user_id, start, end)
    if not entries:
        await callback.answer("За этот период записей нет", show_alert=True)
        return
    if callback_data.fmt == "csv":
        data = entries_to_csv(entries)
    else:
        data = await asyncio.to_thread(entries_to_xlsx, entries, ctx.currency)
    first, last = entries[0].entry_date, entries[-1].entry_date
    if callback_data.period == "all":
        filename = f"finance_all_{ctx.today:%Y-%m-%d}.{callback_data.fmt}"
    else:
        filename = export_filename(start, end, callback_data.fmt)
    label = PERIOD_LABELS.get(callback_data.period, callback_data.period)
    caption = f"📤 {label}: {len(entries)} записей · {format_range(first, last)}"
    document = BufferedInputFile(data, filename=filename)
    await callback.bot.send_document(chat_id_of(callback), document, caption=caption)
    await callback.answer()
