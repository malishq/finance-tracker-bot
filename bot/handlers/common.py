from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from ..config import Config
from ..db import Database
from ..keyboards import CancelCb, main_menu
from ..texts import CANCELLED, GREETING, HELP, NOTHING_TO_CANCEL
from ..utils import respond

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, state: FSMContext) -> None:
    await state.clear()
    await db.ensure_user(message.from_user.id)
    await message.answer(GREETING, reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(HELP, reply_markup=main_menu())


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(NOTHING_TO_CANCEL, reply_markup=main_menu())
        return
    await state.clear()
    await message.answer(CANCELLED, reply_markup=main_menu())


@router.callback_query(CancelCb.filter())
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await respond(callback, CANCELLED)
    await callback.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, config: Config) -> None:
    if message.from_user.id not in config.admin_ids:
        await message.answer("Эта команда доступна только администратору.")
        return
    stats = await db.stats()
    await message.answer(
        "<b>Статистика бота</b>\n"
        f"Пользователей: {stats['users']}\n"
        f"Записей: {stats['entries']}\n"
        f"Включённых напоминаний: {stats['reminders']}"
    )
