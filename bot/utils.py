from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from aiogram import F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from .db import Database
from .keyboards import MENU_BUTTONS
from .services.categories import Category, categories_for, find_by_slug, label_for
from .services.models import INCOME, Entry, UserSettings
from .services.money import fmt_money
from .services.periods import local_today, relative_day


@dataclass
class UserContext:
    settings: UserSettings
    custom: List[Category]
    today: date

    @property
    def user_id(self) -> int:
        return self.settings.user_id

    @property
    def currency(self) -> str:
        return self.settings.currency

    def categories(self, kind: str) -> List[Category]:
        return categories_for(kind, self.custom)

    def category_by_slug(self, slug: str) -> Optional[Category]:
        return find_by_slug(slug, self.custom)

    def label(self, name: str, kind: str) -> str:
        return label_for(name, kind, self.custom)


async def load_context(db: Database, user_id: int) -> UserContext:
    settings = await db.ensure_user(user_id)
    custom = await db.custom_categories(user_id)
    return UserContext(settings=settings, custom=custom, today=local_today(settings.tz_offset))


def esc(text: Optional[str]) -> str:
    return html.escape(text or "")


def plain_text():
    return F.text & ~F.text.in_(MENU_BUTTONS) & ~F.text.startswith("/")


def signed_amount(entry: Entry, currency: str) -> str:
    value = entry.amount if entry.kind == INCOME else -entry.amount
    return fmt_money(value, currency, signed=True)


def entry_line(entry: Entry, ctx: UserContext) -> str:
    description = esc(entry.description) if entry.description else "без описания"
    return (
        f"<b>{signed_amount(entry, ctx.currency)}</b> · {ctx.label(entry.category, entry.kind)} · "
        f"{description} · {relative_day(entry.entry_date, ctx.today)}"
    )


async def safe_edit(message: Message, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" in str(error):
            return
        raise


def chat_id_of(callback: CallbackQuery) -> int:
    if isinstance(callback.message, Message):
        return callback.message.chat.id
    return callback.from_user.id


async def respond(callback: CallbackQuery, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None) -> None:
    if isinstance(callback.message, Message) and callback.message.text is not None:
        await safe_edit(callback.message, text, reply_markup)
    else:
        await callback.bot.send_message(chat_id_of(callback), text, reply_markup=reply_markup)
